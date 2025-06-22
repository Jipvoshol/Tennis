import csv
import re
import json
import os
from datetime import datetime, timedelta
from collections import defaultdict
import itertools
from typing import List, Dict, Tuple
import unicodedata

class HybridPlanningAlgorithm:
    def __init__(self, config_path='planning_config.json'):
        self.spelers = []
        self.banen = []
        self.planning = [] 
        self.ingeplande_spelers_per_week = {}  # Week -> Set van speler IDs
        self.niet_ingeplande_spelers = {}      # Week -> List van speler data
        self.legacy_groepen = []               # Legacy groepen uit vorige seizoenen
        
        # Nieuwe voorkeuren data structuren
        self.samen_met_voorkeuren = {}  # SpelerID -> Set van gewenste partner namen
        self.speler_naam_naar_id = {}   # "Voornaam Achternaam" -> SpelerID
        
        # Dag mapping
        self.dag_mapping = {
            'Maandag': 'Maandag',
            'Dinsdag': 'Dinsdag', 
            'Woensdag': 'Woensdag',
            'Donderdag': 'Donderdag',
            'Vrijdag': 'Vrijdag',
            'Zaterdag': 'Zaterdag',
            'Zondag': 'Zondag'
        }
        
        # Laad configuratie uit JSON bestand
        self.config = self._laad_configuratie(config_path)
        
        # Nieuwe configuratie structuur
        self.harde_filters = self.config['harde_filters']
        self.legacy_scoring = self.config['legacy_scoring']
        self.nieuwe_groep_scoring = self.config['nieuwe_groep_scoring']
        self.optimalisatie_instellingen = self.config['optimalisatie_instellingen']
        self.leeftijdsgroepen = self.config['leeftijdsgroepen']
        self.gender_compensatie = self.config['gender_compensatie']
        self.planning_parameters = self.config['planning_parameters']
        
        # Legacy variabelen voor backwards compatibility
        self.globale_optimalisatie_aan = self.optimalisatie_instellingen['globale_optimalisatie_aan']
        self.max_verbeter_iteraties = self.optimalisatie_instellingen['max_verbeter_iteraties']
        self.min_score_verbetering = self.optimalisatie_instellingen['min_score_verbetering']
        
    def _laad_configuratie(self, config_path):
        """Laad configuratie uit JSON bestand"""
        if not os.path.exists(config_path):
            print(f"Waarschuwing: Configuratiebestand {config_path} niet gevonden. Gebruik standaard instellingen.")
            # Fallback naar hardcoded defaults voor nieuwe structuur
            return {
                "harde_filters": {
                    "groepsgrootte": 4,
                    "max_niveau_verschil": 1,
                    "locatie_strikt": true,
                    "niveau_mix_verplicht": true
                },
                "legacy_scoring": {
                    "volledige_legacy_score": 10.0,
                    "gedeeltelijke_legacy_basis": {
                        "3_van_4": 9.0,
                        "2_van_4": 8.0
                    },
                    "resterende_punten": {
                        "3_van_4": 1.0,
                        "2_van_4": 2.0
                    }
                },
                "nieuwe_groep_scoring": {
                    "niveau_homogeniteit": {
                        "max_punten": 3.0,
                        "scores": {
                            "zelfde_niveau": 3.0,
                            "2_plus_2_mix": 1.5
                        }
                    },
                    "samen_met_voorkeur": {
                        "max_punten": 4.0,
                        "scores": {
                            "3_plus_paren": 4.0,
                            "2_paren": 3.0,
                            "1_paar": 2.0
                        },
                        "wederkerigheid_verplicht": true
                    },
                    "geslachtsbalans": {
                        "max_punten": 2.0,
                        "scores": {
                            "homogeen_4m": 2.0,
                            "homogeen_4v": 2.0,
                            "perfect_2m_2v": 1.5,
                            "drie_een": 0.5
                        }
                    },
                    "leeftijdsmatch": {
                        "max_punten": 1.0,
                        "scores": {
                            "zelfde_categorie": 1.0,
                            "twee_aangrenzend": 0.5
                        }
                    }
                },
                "optimalisatie_instellingen": {
                    "globale_optimalisatie_aan": True,
                    "max_verbeter_iteraties": 10,
                    "min_score_verbetering": 0.1,
                    "minimale_kwaliteitsdrempel": 5.0,
                    "max_niveau_verschil": 1,
                    "max_kandidaten_per_homogene_groep": 8,
                    "excellente_groep_drempel": 9.0,
                    "slechte_groep_drempel": 6.0,
                    "max_swaps_per_week": 10,
                    "max_hersamenstelling_groepen": 5
                },
                "leeftijdsgroepen": {
                    "jong": [18, 30],
                    "middel": [30, 50], 
                    "senior": [50, 70]
                },
                "gender_compensatie": {
                    "dame_niveau_bonus": 1,
                    "omschrijving": "Dame niveau 6 = Heer niveau 7"
                },
                "planning_parameters": {
                    "standaard_aantal_weken": 12,
                    "spelers_per_groep": 4,
                    "performance_cutoff_homogeen": 8,
                    "max_combinaties_check": 16
                }
            }
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                print(f"Configuratie geladen uit: {config_path}")
                return config
        except Exception as e:
            print(f"Fout bij laden configuratie: {e}. Gebruik standaard instellingen.")
            return self._laad_configuratie('non-existent-file')  # Fallback naar defaults

    def laad_spelers(self, bestand_pad):
        """Laad spelers uit CSV bestand"""
        with open(bestand_pad, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            self.spelers = list(reader)
        
        self._bouw_voorkeur_mappings()
        print(f"Geladen: {len(self.spelers)} spelers")
        print(f"SamenMet voorkeuren gevonden voor {len(self.samen_met_voorkeuren)} spelers")
    
    def laad_banen(self, bestand_pad):
        """Laad baanbeschikbaarheid uit CSV bestand"""
        with open(bestand_pad, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            self.banen = [row for row in reader if row['Beschikbaar'].lower() == 'true']
        print(f"Geladen: {len(self.banen)} beschikbare baantijden")
    
    def _bouw_voorkeur_mappings(self):
        """Bouw de voorkeur mappings voor SamenMet functionaliteit"""
        self.samen_met_voorkeuren = {}
        self.speler_naam_naar_id = {}
        
        # Bouw naam mapping
        for speler in self.spelers:
            voornaam = (speler.get('Voornaam', '') or '').strip()
            achternaam = (speler.get('Achternaam', '') or '').strip()
            if voornaam and achternaam:
                norm_naam = self.normalize_name(f"{voornaam} {achternaam}")
                self.speler_naam_naar_id[norm_naam] = speler['SpelerID']
        
        # Parse SamenMet voorkeuren
        for speler in self.spelers:
            samen_met_str = (speler.get('SamenMet', '') or '').strip().replace('"', '')
            if samen_met_str:
                partners = [self.normalize_name(naam) for naam in samen_met_str.split(',') if naam.strip()]
                if partners:
                    self.samen_met_voorkeuren[speler['SpelerID']] = set(partners)
    
    def calculate_group_quality_score(self, groep: List[Dict], locatie: str = None) -> float:
        """Bereken groepskwaliteitsscore met nieuwe scoring systeem"""
        if len(groep) != self.planning_parameters['spelers_per_groep']:
            return 0.0
        
        # DEEL 1: HARDE FILTERS
        if not self._voldoet_aan_harde_filters(groep, locatie):
            return 0.0
        
        # DEEL 2: KWALITEITSSSCORE
        # Check of dit een legacy groep is
        legacy_info = self._bepaal_legacy_status(groep)
        
        if legacy_info['is_legacy']:
            return self._bereken_legacy_score(legacy_info)
        else:
            return self._bereken_nieuwe_groep_score(groep)
    
    def _voldoet_aan_harde_filters(self, groep: List[Dict], locatie: str = None) -> bool:
        """Check of groep voldoet aan alle harde filters"""
        harde_filters = self.config['harde_filters']
        
        # 1. Groepsgrootte
        if len(groep) != harde_filters['groepsgrootte']:
            return False
        
        # 2. Locatie (alleen checken als locatie_strikt = true en locatie is opgegeven)
        if harde_filters['locatie_strikt'] and locatie:
            # Check of alle spelers dezelfde locatie voorkeur hebben
            for speler in groep:
                if speler['LocatieVoorkeur'] != locatie:
                    return False
        
        # 3. Niveau verschil
        niveaus = [float(s['Niveau']) for s in groep if s['Niveau']]
        if niveaus:
            niveau_verschil = max(niveaus) - min(niveaus)
            if niveau_verschil > harde_filters['max_niveau_verschil']:
                return False
        
        # 4. Niveau mix samenstelling
        if harde_filters['niveau_mix_verplicht'] and len(set(niveaus)) > 1:
            niveau_counts = {}
            for niveau in niveaus:
                niveau_counts[niveau] = niveau_counts.get(niveau, 0) + 1
            
            # Check of precies 2 van elk niveau
            for count in niveau_counts.values():
                if count != 2:
                    return False
        
        return True
    
    def _bepaal_legacy_status(self, groep: List[Dict]) -> Dict:
        """Bepaal of dit een legacy groep is en hoeveel spelers blijven"""
        # Voor nu: simpele implementatie - check of spelers "BlijftInHuidigeGroep" hebben
        blijvende_spelers = [s for s in groep if s.get('BlijftInHuidigeGroep', '').lower() == 'ja']
        
        return {
            'is_legacy': len(blijvende_spelers) >= 2,
            'aantal_blijvend': len(blijvende_spelers),
            'totaal_origineel': 4,  # Voor nu aanname van 4
            'groep': groep  # Voeg de groep toe voor scoring berekening
        }
    
    def _bereken_legacy_score(self, legacy_info: Dict) -> float:
        """Bereken score voor legacy groepen"""
        legacy_scoring = self.config['legacy_scoring']
        
        if legacy_info['aantal_blijvend'] == 4:
            score = legacy_scoring['volledige_legacy_score']
            return score
        elif legacy_info['aantal_blijvend'] == 3:
            basis_score = legacy_scoring['gedeeltelijke_legacy_basis']['3_van_4']
            resterende_punten = legacy_scoring['resterende_punten']['3_van_4']
        elif legacy_info['aantal_blijvend'] == 2:
            basis_score = legacy_scoring['gedeeltelijke_legacy_basis']['2_van_4']
            resterende_punten = legacy_scoring['resterende_punten']['2_van_4']
        else:
            return 0.0
        
        # Bereken score voor gedeeltelijke legacy groepen volgens de formule:
        # Eindscore = basis_score + (behaalde_punten / maximaal_haalbare_punten) × resterende_punten
        
        # Haal de groep op uit de legacy_info (dit moet worden toegevoegd aan de legacy_info)
        groep = legacy_info.get('groep', [])
        if not groep:
            return basis_score
        
        # Bereken score voor de overige componenten (zonder SamenMet voorkeuren)
        scoring = self.config['nieuwe_groep_scoring']
        
        # 1. Niveau homogeniteit
        niveau_score = self._bereken_niveau_score(groep, scoring['niveau_homogeniteit'])
        
        # 2. Geslachtsbalans
        geslacht_score = self._bereken_geslacht_score(groep, scoring['geslachtsbalans'])
        
        # 3. Leeftijdsmatch
        leeftijd_score = self._bereken_leeftijd_score(groep, scoring['leeftijdsmatch'])
        
        # Totaal behaalde punten uit overige componenten
        behaalde_punten = niveau_score + geslacht_score + leeftijd_score
        
        # Maximale haalbare punten uit overige componenten
        maximaal_haalbare_punten = (scoring['niveau_homogeniteit']['max_punten'] + 
                                   scoring['geslachtsbalans']['max_punten'] + 
                                   scoring['leeftijdsmatch']['max_punten'])
        
        # Bereken eindscore volgens de formule
        if maximaal_haalbare_punten > 0:
            eindscore = basis_score + (behaalde_punten / maximaal_haalbare_punten) * resterende_punten
        else:
            eindscore = basis_score
        
        return min(eindscore, 10.0)
    
    def _bereken_nieuwe_groep_score(self, groep: List[Dict]) -> float:
        """Bereken score voor nieuwe groepen"""
        scoring = self.config['nieuwe_groep_scoring']
        totaal_score = 0.0
        
        # 1. Niveau homogeniteit
        totaal_score += self._bereken_niveau_score(groep, scoring['niveau_homogeniteit'])
        
        # 2. Samen-met voorkeur
        totaal_score += self._bereken_samen_met_score(groep, scoring['samen_met_voorkeur'])
        
        # 3. Geslachtsbalans
        totaal_score += self._bereken_geslacht_score(groep, scoring['geslachtsbalans'])
        
        # 4. Leeftijdsmatch
        totaal_score += self._bereken_leeftijd_score(groep, scoring['leeftijdsmatch'])
        
        return min(totaal_score, 10.0)
    
    def _bereken_niveau_score(self, groep: List[Dict], scoring_config: Dict) -> float:
        """Bereken niveau homogeniteit score"""
        niveaus = [float(s['Niveau']) for s in groep if s['Niveau']]
        if not niveaus:
            return 0.0
        
        if len(set(niveaus)) == 1:
            return scoring_config['scores']['zelfde_niveau']
        elif len(set(niveaus)) == 2:
            # Check of het 2+2 mix is
            niveau_counts = {}
            for niveau in niveaus:
                niveau_counts[niveau] = niveau_counts.get(niveau, 0) + 1
            
            if all(count == 2 for count in niveau_counts.values()):
                return scoring_config['scores']['2_plus_2_mix']
        
        return 0.0
    
    def _bereken_samen_met_score(self, groep: List[Dict], scoring_config: Dict) -> float:
        """Bereken SamenMet voorkeur score met wederkerigheid"""
        if not scoring_config['wederkerigheid_verplicht']:
            return self._bereken_oude_samen_met_score(groep)
        
        # Tel wederzijdse paren
        wederzijdse_paren = 0
        groep_ids = {s['SpelerID'] for s in groep}
        norm_namen = {s['SpelerID']: self.normalize_name(f"{s['Voornaam']} {s['Achternaam']}") for s in groep}
        
        for speler in groep:
            speler_id = speler['SpelerID']
            if speler_id in self.samen_met_voorkeuren:
                for partner_norm_naam in self.samen_met_voorkeuren[speler_id]:
                    partner_id = self.speler_naam_naar_id.get(partner_norm_naam)
                    if partner_id and partner_id in groep_ids:
                        # Check wederkerigheid
                        if (partner_id in self.samen_met_voorkeuren and 
                            norm_namen[speler_id] in self.samen_met_voorkeuren[partner_id]):
                            wederzijdse_paren += 1
        
        # Delen door 2 omdat elk paar dubbel geteld wordt
        wederzijdse_paren //= 2
        
        if wederzijdse_paren >= 3:
            return scoring_config['scores']['3_plus_paren']
        elif wederzijdse_paren == 2:
            return scoring_config['scores']['2_paren']
        elif wederzijdse_paren == 1:
            return scoring_config['scores']['1_paar']
        
        return 0.0
    
    def _bereken_oude_samen_met_score(self, groep: List[Dict]) -> float:
        """Oude SamenMet scoring voor backwards compatibility"""
        voorkeur_score = self._bereken_voorkeur_score(groep)
        return min(voorkeur_score * 4.0, 4.0)
    
    def _bereken_geslacht_score(self, groep: List[Dict], scoring_config: Dict) -> float:
        """Bereken geslachtsbalans score"""
        mannen = sum(1 for s in groep if s['Geslacht'] in ['M', 'Man', 'Jongen'])
        vrouwen = len(groep) - mannen
        
        if mannen == 4:
            return scoring_config['scores']['homogeen_4m']
        elif vrouwen == 4:
            return scoring_config['scores']['homogeen_4v']
        elif mannen == 2 and vrouwen == 2:
            return scoring_config['scores']['perfect_2m_2v']
        elif mannen == 3 or vrouwen == 3:
            return scoring_config['scores']['drie_een']
        
        return 0.0
    
    def _bereken_leeftijd_score(self, groep: List[Dict], scoring_config: Dict) -> float:
        """Bereken leeftijdsmatch score"""
        leeftijden = []
        for speler in groep:
            try:
                leeftijd = int(speler.get('Leeftijd', ''))
                leeftijden.append(leeftijd)
            except (ValueError, TypeError):
                continue
        
        if len(leeftijden) < 4:
            return 0.0
        
        # Groepeer leeftijden
        groepen = set()
        for l in leeftijden:
            jong_min, jong_max = self.leeftijdsgroepen["jong"]
            middel_min, middel_max = self.leeftijdsgroepen["middel"]
            senior_min, senior_max = self.leeftijdsgroepen["senior"]
            
            if jong_min <= l < jong_max:
                groepen.add("jong")
            elif middel_min <= l < middel_max:
                groepen.add("middel")
            elif senior_min <= l <= senior_max:
                groepen.add("senior")
            else:
                groepen.add("overig")
        
        if len(groepen) == 1:
            return scoring_config['scores']['zelfde_categorie']
        elif len(groepen) == 2:
            return scoring_config['scores']['twee_aangrenzend']
        
        return 0.0
    
    def _bereken_voorkeur_score(self, groep: List[Dict]) -> float:
        """Bereken SamenMet voorkeuren score (oude methode voor backwards compatibility)"""
        groep_namen = set()
        for speler in groep:
            voornaam = (speler.get('Voornaam', '') or '').strip()
            achternaam = (speler.get('Achternaam', '') or '').strip()
            if voornaam and achternaam:
                groep_namen.add(f"{voornaam} {achternaam}".lower())
        
        vervulde_voorkeuren = 0
        totale_voorkeuren = 0
        
        for speler in groep:
            if speler['SpelerID'] in self.samen_met_voorkeuren:
                partners = self.samen_met_voorkeuren[speler['SpelerID']]
                totale_voorkeuren += len(partners)
                vervulde_voorkeuren += sum(1 for partner in partners if partner in groep_namen)
        
        return vervulde_voorkeuren / totale_voorkeuren if totale_voorkeuren > 0 else 0.0
    
    def _bereken_gender_niveau_compensatie(self, groep: List[Dict]) -> float:
        """Bereken niveau compensatie"""
        mannen = [s for s in groep if s['Geslacht'] in ['M', 'Man', 'Jongen']]
        vrouwen = [s for s in groep if s['Geslacht'] in ['V', 'Vrouw', 'Meisje']]
        
        if len(mannen) == 0 or len(vrouwen) == 0:
            # Homogene groep
            niveaus = [float(s['Niveau']) for s in groep if s['Niveau']]
            if not niveaus:
                return self.config["niveau_scores"]["slechte_niveau_match"]
            verschil = max(niveaus) - min(niveaus)
            if verschil == 0:
                return self.config["niveau_scores"]["perfect_niveau_match"]
            elif verschil <= self.optimalisatie_instellingen['max_niveau_verschil']:
                return self.config["niveau_scores"]["goede_niveau_match"]
            else:
                return self.config["niveau_scores"]["slechte_niveau_match"]
        
        # Gemengde groep - gender compensatie uit configuratie
        niveaus = ([float(m['Niveau']) for m in mannen if m['Niveau']] + 
                  [float(v['Niveau']) + self.gender_compensatie['dame_niveau_bonus'] for v in vrouwen if v['Niveau']])
        if not niveaus:
            return self.config["niveau_scores"]["slechte_niveau_match"]
        verschil = max(niveaus) - min(niveaus)
        if verschil == 0:
            return self.config["niveau_scores"]["perfect_niveau_match"]
        elif verschil <= self.optimalisatie_instellingen['max_niveau_verschil']:
            return self.config["niveau_scores"]["goede_niveau_match"]
        else:
            return self.config["niveau_scores"]["slechte_niveau_match"]

    def parse_tijdslot(self, tijdslot_str):
        """Parse tijdslot string"""
        if not tijdslot_str or tijdslot_str.strip() == 'Niet beschikbaar':
            return []
        
        slots = []
        for slot in tijdslot_str.split(','):
            slot = slot.strip()
            if '-' in slot:
                try:
                    start, eind = slot.split('-')
                    slots.append((start.strip(), eind.strip()))
                except:
                    continue
        return slots
    
    def tijden_overlappen(self, slot1, slot2):
        """Check tijdslot overlap"""
        def tijd_naar_minuten(tijd_str):
            uur, minuut = map(int, tijd_str.split(':'))
            return uur * 60 + minuut
        
        start1, eind1 = slot1
        start2, eind2 = slot2
        start1_min, eind1_min = tijd_naar_minuten(start1), tijd_naar_minuten(eind1)
        start2_min, eind2_min = tijd_naar_minuten(start2), tijd_naar_minuten(eind2)
        
        return not (eind1_min <= start2_min or eind2_min <= start1_min)

    def optimize_groups_in_slot(self, spelers: List[Dict], max_groepen: int, locatie: str = None) -> List[List[Dict]]:
        """Optimaliseer groepsvorming in tijdslot"""
        if len(spelers) < 4:
            return []
        
        mannen = [s for s in spelers if s['Geslacht'] in ['M', 'Man', 'Jongen']]
        vrouwen = [s for s in spelers if s['Geslacht'] in ['V', 'Vrouw', 'Meisje']]
        
        mannen.sort(key=lambda x: float(x['Niveau']) if x['Niveau'] else 0)
        vrouwen.sort(key=lambda x: float(x['Niveau']) if x['Niveau'] else 0)
        
        # Maak homogene groepen
        alle_groepen = []
        alle_groepen.extend(self._maak_homogene_groepen(mannen, max_groepen // 2, locatie))
        
        # Verwijder gebruikte spelers
        gebruikt = set()
        for groep in alle_groepen:
            for speler in groep:
                gebruikt.add(speler['SpelerID'])
        
        resterende_mannen = [m for m in mannen if m['SpelerID'] not in gebruikt]
        resterende_vrouwen = [v for v in vrouwen if v['SpelerID'] not in gebruikt]
        
        alle_groepen.extend(self._maak_homogene_groepen(resterende_vrouwen, max_groepen - len(alle_groepen), locatie))
        
        # Verwijder meer gebruikte spelers
        for groep in alle_groepen:
            for speler in groep:
                gebruikt.add(speler['SpelerID'])
        
        resterende_mannen = [m for m in resterende_mannen if m['SpelerID'] not in gebruikt]
        resterende_vrouwen = [v for v in vrouwen if v['SpelerID'] not in gebruikt]
        
        # Maak gemengde groepen
        alle_groepen.extend(self._maak_gemengde_groepen(resterende_mannen, resterende_vrouwen, max_groepen - len(alle_groepen), locatie))
        
        # Score en sorteer - BELANGRIJK: Filter groepen met score 0.0 uit
        groepen_met_scores = []
        for groep in alle_groepen:
            score = self.calculate_group_quality_score(groep, locatie)
            if score > 0.0:  # Alleen groepen die voldoen aan harde filters
                groepen_met_scores.append((groep, score))
        
        groepen_met_scores.sort(key=lambda x: x[1], reverse=True)
        
        return [groep for groep, _ in groepen_met_scores[:max_groepen]]
    
    def _maak_homogene_groepen(self, spelers: List[Dict], max_groepen: int, locatie: str = None) -> List[List[Dict]]:
        """Maak homogene groepen"""
        if len(spelers) < 4 or max_groepen == 0:
            return []
        
        groepen = []
        spelers_sorted = sorted(spelers, key=lambda x: float(x['Niveau']) if x['Niveau'] else 0)
        
        while len(spelers_sorted) >= 4 and len(groepen) < max_groepen:
            beste_groep = None
            beste_score = -1
            
            for groep in itertools.combinations(spelers_sorted[:16], 4):
                niveaus = [float(s['Niveau']) for s in groep if s['Niveau']]
                if niveaus and max(niveaus) - min(niveaus) <= 1:
                    score = self.calculate_group_quality_score(list(groep), locatie)
                    if score > 0.0 and score > beste_score:  # Alleen groepen met score > 0
                        beste_score = score
                        beste_groep = list(groep)
            
            if beste_groep:
                groepen.append(beste_groep)
                for speler in beste_groep:
                    spelers_sorted.remove(speler)
            else:
                break
        
        return groepen
    
    def create_optimized_homogene_groups(self, spelers: List[Dict], max_groepen: int, locatie: str = None) -> List[List[Dict]]:
        """Maak geoptimaliseerde homogene groepen met niveau-optimalisatie"""
        if len(spelers) < self.planning_parameters['spelers_per_groep'] or max_groepen == 0:
            return []
        
        groepen = []
        spelers_sorted = sorted(spelers, key=lambda x: float(x['Niveau']) if x['Niveau'] else 0)
        
        # Genereer alle mogelijke combinaties en evalueer ze
        while len(spelers_sorted) >= self.planning_parameters['spelers_per_groep'] and len(groepen) < max_groepen:
            # Probeer de beste groep te vinden met huidige spelers
            beste_groep = None
            beste_score = -1
            
            # Beperk combinaties tot redelijk aantal (performance) - nu configureerbaar
            max_kandidaten = min(self.optimalisatie_instellingen['max_kandidaten_per_homogene_groep'], len(spelers_sorted))
            kandidaten = spelers_sorted[:max_kandidaten]
            
            for groep in itertools.combinations(kandidaten, self.planning_parameters['spelers_per_groep']):
                groep_list = list(groep)
                niveaus = [float(s['Niveau']) for s in groep_list if s['Niveau']]
                
                # Alleen groepen met max niveau verschil - nu configureerbaar
                if niveaus and max(niveaus) - min(niveaus) <= self.optimalisatie_instellingen['max_niveau_verschil']:
                    score = self.calculate_group_quality_score(groep_list, locatie)
                    if score > 0.0 and score > beste_score:  # Alleen groepen met score > 0
                        beste_score = score
                        beste_groep = groep_list
            
            if beste_groep:
                groepen.append(beste_groep)
                # Verwijder gebruikte spelers
                for speler in beste_groep:
                    if speler in spelers_sorted:
                        spelers_sorted.remove(speler)
            else:
                # Geen geldige groep meer mogelijk
                break
        
        return groepen
    
    def _maak_gemengde_groepen(self, mannen: List[Dict], vrouwen: List[Dict], max_groepen: int, locatie: str = None) -> List[List[Dict]]:
        """Maak gemengde groepen"""
        if len(mannen) < 2 or len(vrouwen) < 2 or max_groepen == 0:
            return []
        
        groepen = []
        mannen_per_niveau = defaultdict(list)
        vrouwen_per_niveau = defaultdict(list)
        
        for man in mannen:
            if man['Niveau']:
                niveau = float(man['Niveau'])
                mannen_per_niveau[niveau].append(man)
        for vrouw in vrouwen:
            if vrouw['Niveau']:
                niveau = float(vrouw['Niveau'])
                vrouwen_per_niveau[niveau].append(vrouw)
        
        for vrouw_niveau in sorted(vrouwen_per_niveau.keys()):
            if len(groepen) >= max_groepen:
                break
                
            beschikbare_vrouwen = vrouwen_per_niveau[vrouw_niveau]
            if len(beschikbare_vrouwen) < 2:
                continue
            
            for man_niveau in [vrouw_niveau + self.gender_compensatie['dame_niveau_bonus'], vrouw_niveau]:
                if len(groepen) >= max_groepen:
                    break
                    
                beschikbare_mannen = mannen_per_niveau.get(man_niveau, [])
                if len(beschikbare_mannen) < 2:
                    continue
                
                while (len(beschikbare_mannen) >= 2 and len(beschikbare_vrouwen) >= 2 and 
                       len(groepen) < max_groepen):
                    
                    groep = beschikbare_mannen[:2] + beschikbare_vrouwen[:2]
                    # Alleen groepen met score > 0 (die voldoen aan harde filters)
                    score = self.calculate_group_quality_score(groep, locatie)
                    if score > 0.0:
                        groepen.append(groep)
                        beschikbare_mannen = beschikbare_mannen[2:]
                        beschikbare_vrouwen = beschikbare_vrouwen[2:]
                        mannen_per_niveau[man_niveau] = beschikbare_mannen
                        vrouwen_per_niveau[vrouw_niveau] = beschikbare_vrouwen
                    else:
                        break
                        
        return groepen

    def vind_matches(self, dag, week_nummer):
        """Vind matches voor een dag"""
        dag_key = dag.capitalize()
        
        # Groepeer banen per locatie/tijdslot
        baan_objecten_per_slot = defaultdict(list)
        for baan in self.banen:
            if baan['Dag'].capitalize() == dag_key:
                slot_key = (baan['Locatie'], baan['Tijdslot'])
                baan_objecten_per_slot[slot_key].append(baan)
        
        matches = []
        if week_nummer not in self.ingeplande_spelers_per_week:
            self.ingeplande_spelers_per_week[week_nummer] = set()
        ingeplande_ids = self.ingeplande_spelers_per_week[week_nummer]
        
        for (locatie, tijdslot_str), banen_lijst in baan_objecten_per_slot.items():
            if not banen_lijst:
                continue
            
            try:
                tijdslot_start, tijdslot_eind = tijdslot_str.split('-')
            except ValueError:
                continue

            # Verzamel beschikbare spelers
            beschikbare_spelers = []
            for speler in self.spelers:
                if speler['SpelerID'] in ingeplande_ids:
                    continue
                
                # Check tijdbeschikbaarheid
                speler_tijden = self.parse_tijdslot(speler.get(dag_key, ''))
                is_beschikbaar = any(
                    self.tijden_overlappen((tijdslot_start, tijdslot_eind), (start, eind))
                    for start, eind in speler_tijden
                )
                
                if not is_beschikbaar:
                    continue
                
                # Check locatie flexibiliteit
                heeft_locatie = speler['LocatieVoorkeur'] == locatie
                heeft_voorkeuren = speler['SpelerID'] in self.samen_met_voorkeuren
                
                if heeft_locatie or heeft_voorkeuren:
                    speler_copy = speler.copy()
                    speler_copy['_locatie_flexible'] = not heeft_locatie
                    beschikbare_spelers.append(speler_copy)
            
            # Optimaliseer groepen
            if len(beschikbare_spelers) >= 4 and banen_lijst:
                groepen = self.optimize_groups_in_slot(beschikbare_spelers, len(banen_lijst), locatie)
                
                for i, groep in enumerate(groepen):
                    if i >= len(banen_lijst):
                        break
                    
                    # Markeer spelers als ingepland
                    for speler in groep:
                        ingeplande_ids.add(speler['SpelerID'])
                    
                    # Bepaal karakteristieken
                    mannen_count = sum(1 for s in groep if s['Geslacht'] in ['M', 'Man', 'Jongen'])
                    vrouwen_count = 4 - mannen_count
                    
                    if mannen_count == 2 and vrouwen_count == 2:
                        gender_balans = 'Perfect (2M/2V)'
                    elif mannen_count == 4:
                        gender_balans = 'Homogeen (4M)'
                    elif vrouwen_count == 4:
                        gender_balans = 'Homogeen (4V)'
                    else:
                        gender_balans = f'Anders (M:{mannen_count}, V:{vrouwen_count})'
                    
                    niveaus = [float(s['Niveau']) for s in groep if s['Niveau']]
                    if niveaus:
                        if len(set(niveaus)) == 1:
                            niveau = str(int(niveaus[0]))
                        else:
                            niveau = f"{int(min(niveaus))}-{int(max(niveaus))} (gemengd)"
                    else:
                        niveau = "Onbekend"
                    
                    matches.append({
                        'week': week_nummer,
                        'day': dag,
                        'location': locatie,
                        'time': tijdslot_str,
                        'baan': banen_lijst[i]['BaanNaam'],
                        'group': ', '.join([f"{s['Voornaam']} {s['Achternaam']}" for s in groep]),
                        'speler_ids': [s['SpelerID'] for s in groep],
                        'group_size': 4,
                        'niveau': niveau,
                        'gender_balans': gender_balans,
                        'quality_score': self.calculate_group_quality_score(groep, locatie),
                        'flexible_players': sum(1 for s in groep if s.get('_locatie_flexible', False))
                    })
                    
                    # Check of dit een legacy groep is en voeg legacy velden toe
                    legacy_info = self._bepaal_legacy_status(groep)
                    if legacy_info['is_legacy']:
                        is_volledig_legacy = legacy_info['aantal_blijvend'] == legacy_info['totaal_origineel']
                        if is_volledig_legacy:
                            matches[-1]['legacy'] = True
                            matches[-1]['legacy_type'] = 'legacy_volledig'
                        else:
                            matches[-1]['legacy'] = True
                            matches[-1]['legacy_type'] = 'legacy_gedeeltelijk'
                    else:
                        matches[-1]['legacy'] = False
                        matches[-1]['legacy_type'] = ''
        
        return matches

    def vind_niet_ingeplande_spelers(self, week_nummer):
        """Vind niet-ingeplande spelers"""
        ingeplande_ids = self.ingeplande_spelers_per_week.get(week_nummer, set())
        niet_ingepland = []
        
        for speler in self.spelers:
            if speler['SpelerID'] not in ingeplande_ids:
                niet_ingepland.append({
                    'SpelerID': speler['SpelerID'],
                    'Naam': f"{speler['Voornaam']} {speler['Achternaam']}",
                    'LocatieVoorkeur': speler['LocatieVoorkeur'],
                    'Niveau': speler['Niveau']
                })
        
        self.niet_ingeplande_spelers[week_nummer] = niet_ingepland
        return niet_ingepland

    def maak_planning_meerdere_weken(self, aantal_weken=12):
        """Maak planning voor meerdere weken met legacy groepen ondersteuning"""
        self.planning = []
        self.ingeplande_spelers_per_week = {}
        self.niet_ingeplande_spelers = {}
        
        # FASE 0: Plan legacy groepen eerst in (als beschikbaar)
        if self.legacy_groepen:
            self.plan_legacy_groepen(aantal_weken)
        
        # Inclusief weekend dagen
        dagen = ['Maandag', 'Dinsdag', 'Woensdag', 'Donderdag', 'Vrijdag', 'Zaterdag', 'Zondag']
        
        print("=== FASE 1: LOKALE OPTIMALISATIE ===")
        for week_nummer in range(1, aantal_weken + 1):
            print(f"Planning week {week_nummer}...")
            if week_nummer not in self.ingeplande_spelers_per_week:
                self.ingeplande_spelers_per_week[week_nummer] = set()
            
            for dag in dagen:
                matches = self.vind_matches(dag, week_nummer)
                self.planning.extend(matches)
            
            niet_ingepland = self.vind_niet_ingeplande_spelers(week_nummer)
            ingepland_count = len(self.ingeplande_spelers_per_week.get(week_nummer, set()))
            print(f"  Week {week_nummer}: {ingepland_count} spelers ingepland, {len(niet_ingepland)} niet ingepland")
        
        print(f"\nLokale optimalisatie voltooid: {len(self.planning)} trainingen over {aantal_weken} weken")
        
        if self.globale_optimalisatie_aan:
            print("\n=== FASE 2: GLOBALE OPTIMALISATIE ===")
            self.voer_globale_optimalisatie_uit()
        
        print(f"\nTotale planning na optimalisatie: {len(self.planning)} trainingen over {aantal_weken} weken")
        return self.planning

    def voer_globale_optimalisatie_uit(self):
        """Globale optimalisatie"""
        print("Start globale optimalisatie...")
        
        for iteratie in range(self.max_verbeter_iteraties):
            print(f"  Iteratie {iteratie + 1}/{self.max_verbeter_iteraties}")
            
            verbeteringen = 0
            
            # Groep verplaatsing
            print(f"    Fase 1: Groep verplaatsing...")
            verplaatsingen = self._voer_groep_verplaatsing_fase_uit()
            verbeteringen += verplaatsingen
            print(f"      {verplaatsingen} groep verplaatsingen")
            
            # Speler swapping
            print(f"    Fase 2: Speler swapping...")
            swaps = self._voer_speler_swapping_uit()
            verbeteringen += swaps
            print(f"      {swaps} speler swaps")
            
            # Groep hersamenstelling (alleen bij weinig verbeteringen)
            if verbeteringen < 2:
                print(f"    Fase 3: Groep hersamenstelling...")
                hersamenstelling = self._voer_groep_hersamenstelling_uit()
                verbeteringen += hersamenstelling
                print(f"      {hersamenstelling} groep hersamensstellingen")
            
            print(f"    Totaal: {verbeteringen} verbeteringen gevonden")
            
            if verbeteringen == 0:
                print("  Geen verdere verbeteringen mogelijk, stoppen met optimalisatie")
                break
        
        print("Globale optimalisatie voltooid")

    def _voer_groep_verplaatsing_fase_uit(self) -> int:
        """Voer groep verplaatsing uit"""
        verbeteringen = 0
        planning_gesorteerd = sorted(self.planning, key=lambda x: x.get('quality_score', 0.0))
        
        for match in planning_gesorteerd:
            # Skip legacy groepen - deze blijven intact
            if match.get('legacy', False):
                continue
                
            # Gebruik configuratie waarde voor excellente groep drempel
            if match.get('quality_score', 0.0) >= self.optimalisatie_instellingen['excellente_groep_drempel']:
                continue
            
            beste_alternatief = self._vind_beste_alternatief_tijdslot(match)
            if (beste_alternatief and 
                beste_alternatief['score'] > match.get('quality_score', 0.0) + self.min_score_verbetering):
                if self._voer_groep_verplaatsing_uit(match, beste_alternatief):
                    verbeteringen += 1
        
        return verbeteringen

    def _voer_speler_swapping_uit(self) -> int:
        """Voer speler swapping uit"""
        verbeteringen = 0
        matches_per_week = defaultdict(list)
        
        for match in self.planning:
            matches_per_week[match['week']].append(match)
        
        for week_matches in matches_per_week.values():
            if len(week_matches) < 2:
                continue
                
            week_swaps = 0
            for i, match1 in enumerate(week_matches):
                for match2 in week_matches[i+1:]:
                    # Gebruik configuratie waarde voor max swaps per week
                    if week_swaps >= self.optimalisatie_instellingen['max_swaps_per_week']:
                        break
                    if self._probeer_speler_swap_tussen_groepen(match1, match2):
                        verbeteringen += 1
                        week_swaps += 1
                # Gebruik configuratie waarde voor max swaps per week
                if week_swaps >= self.optimalisatie_instellingen['max_swaps_per_week']:
                    break
        
        return verbeteringen

    def _voer_groep_hersamenstelling_uit(self) -> int:
        """Voer groep hersamenstelling uit"""
        improvements = 0
        matches_per_week = defaultdict(list)
        
        for match in self.planning:
            matches_per_week[match['week']].append(match)
        
        for week_matches in matches_per_week.values():
            # Gebruik configuratie waarde voor slechte groep drempel
            poor_matches = [m for m in week_matches if m.get('quality_score', 0.0) < self.optimalisatie_instellingen['slechte_groep_drempel'] and not m.get('legacy', False)]
            if len(poor_matches) >= 2:
                poor_matches.sort(key=lambda x: x.get('quality_score', 0.0))
                # Gebruik configuratie waarde voor max hersamenstelling groepen
                max_groepen = self.optimalisatie_instellingen['max_hersamenstelling_groepen']
                if self._try_group_reassembly_for_week(poor_matches[:max_groepen]):
                    improvements += len(poor_matches[:max_groepen])
        
        return improvements

    def _vind_beste_alternatief_tijdslot(self, huidige_match: Dict) -> Dict:
        """Vind beste alternatief tijdslot"""
        spelers = self._haal_spelers_uit_match(huidige_match)
        huidige_score = huidige_match.get('quality_score', 0.0)
        beste_alternatief = None
        beste_score = huidige_score
        
        # Gebruik alle dagen inclusief weekend voor optimalisatie
        for dag in ['Maandag', 'Dinsdag', 'Woensdag', 'Donderdag', 'Vrijdag']:
            dag_key = dag.capitalize()
            for baan in self.banen:
                if (baan['Dag'].capitalize() == dag_key and 
                    not (dag == huidige_match['day'] and 
                         baan['Locatie'] == huidige_match['location'] and 
                         baan['Tijdslot'] == huidige_match['time'])):
                    
                    if (self._zijn_alle_spelers_beschikbaar(spelers, dag_key, baan['Tijdslot'], baan['Locatie']) and
                        self._is_baan_beschikbaar(huidige_match['week'], dag, baan['Locatie'], baan['Tijdslot'], baan['BaanNaam'])):
                        
                        score = self._bereken_score_voor_tijdslot(spelers, dag, baan['Locatie'], baan['Tijdslot'])
                        if score > beste_score:
                            beste_score = score
                            beste_alternatief = {
                                'week': huidige_match['week'],
                                'day': dag,
                                'location': baan['Locatie'],
                                'time': baan['Tijdslot'],
                                'baan': baan['BaanNaam'],
                                'score': score
                            }
        
        return beste_alternatief

    def _haal_spelers_uit_match(self, match: Dict) -> List[Dict]:
        """Haal spelers uit match"""
        speler_ids = match['speler_ids']
        return [s for s in self.spelers if s['SpelerID'] in speler_ids]

    def _zijn_alle_spelers_beschikbaar(self, spelers: List[Dict], dag_key: str, tijdslot_str: str, locatie: str) -> bool:
        """Check of alle spelers beschikbaar zijn"""
        # Fix voor legacy tijdslots: converteer enkele tijdstip naar bereik
        if '-' not in tijdslot_str and ':' in tijdslot_str:
            # Single time zoals "18:00" -> maak er "18:00-19:00" van
            try:
                start_tijd = tijdslot_str.strip()
                start_uur = int(start_tijd.split(':')[0])
                eind_uur = start_uur + 1
                tijdslot_str = f"{start_tijd}-{eind_uur:02d}:00"
            except:
                pass
        
        try:
            tijdslot_start, tijdslot_eind = tijdslot_str.split('-')
        except ValueError:
            return False
        
        for speler in spelers:
            # Check tijd
            speler_tijden = self.parse_tijdslot(speler.get(dag_key, ''))
            tijd_overlap = any(self.tijden_overlappen((tijdslot_start, tijdslot_eind), (start, eind)) 
                              for start, eind in speler_tijden)
            if not tijd_overlap:
                return False
            
            # Check locatie - meer flexibel voor legacy groepen
            heeft_locatie = speler['LocatieVoorkeur'] == locatie
            heeft_voorkeuren = speler['SpelerID'] in self.samen_met_voorkeuren
            
            # Voor legacy groepen: accepteer ook spelers die geen stricte locatie voorkeur hebben
            if not (heeft_locatie or heeft_voorkeuren):
                return False
        
        return True

    def _is_baan_beschikbaar(self, week: int, dag: str, locatie: str, tijdslot: str, baan_naam: str) -> bool:
        """Check of baan beschikbaar is"""
        return not any(
            m['week'] == week and m['day'] == dag and m['location'] == locatie and 
            m['time'] == tijdslot and m['baan'] == baan_naam
            for m in self.planning
        )

    def _bereken_score_voor_tijdslot(self, spelers: List[Dict], dag: str, locatie: str, tijdslot: str) -> float:
        """Bereken score voor tijdslot"""
        basis_score = self.calculate_group_quality_score(spelers)
        # Voor nu: geen locatie bonus meer - dit wordt gecheckt in harde filters
        return min(basis_score, 10.0)

    def _voer_groep_verplaatsing_uit(self, oude_match: Dict, nieuwe_match: Dict) -> bool:
        """Voer groep verplaatsing uit"""
        for i, match in enumerate(self.planning):
            if (match['week'] == oude_match['week'] and match['day'] == oude_match['day'] and
                match['location'] == oude_match['location'] and match['time'] == oude_match['time'] and
                match['baan'] == oude_match['baan']):
                
                self.planning[i].update({
                    'day': nieuwe_match['day'],
                    'location': nieuwe_match['location'],
                    'time': nieuwe_match['time'],
                    'baan': nieuwe_match['baan'],
                    'quality_score': nieuwe_match['score']
                })
                return True
        return False

    def _probeer_speler_swap_tussen_groepen(self, match1: Dict, match2: Dict) -> bool:
        """Probeert de beste speler-swap te vinden tussen twee groepen en voert deze uit"""
        
        # Voorkom swaps met legacy groepen
        if match1.get('legacy', False) or match2.get('legacy', False):
            return False

        spelers1 = self._haal_spelers_uit_match(match1)
        spelers2 = self._haal_spelers_uit_match(match2)
        
        huidige_totaal = match1.get('quality_score', 0.0) + match2.get('quality_score', 0.0)
        beste_verbetering = 0.0
        beste_swap = None
        
        for i, speler1 in enumerate(spelers1):
            for j, speler2 in enumerate(spelers2):
                if self._is_speler_swap_toegestaan(speler1, speler2, match1, match2):
                    nieuwe_groep1 = spelers1.copy()
                    nieuwe_groep2 = spelers2.copy()
                    nieuwe_groep1[i] = speler2
                    nieuwe_groep2[j] = speler1
                    
                    nieuwe_score1 = self.calculate_group_quality_score(nieuwe_groep1)
                    nieuwe_score2 = self.calculate_group_quality_score(nieuwe_groep2)
                    nieuwe_totaal = nieuwe_score1 + nieuwe_score2
                    
                    verbetering = nieuwe_totaal - huidige_totaal
                    if (verbetering > beste_verbetering and 
                        verbetering >= self.min_score_verbetering and
                        nieuwe_score1 >= self.optimalisatie_instellingen['minimale_kwaliteitsdrempel'] and
                        nieuwe_score2 >= self.optimalisatie_instellingen['minimale_kwaliteitsdrempel']):
                        beste_verbetering = verbetering
                        beste_swap = {
                            'i': i, 'j': j,
                            'groep1': nieuwe_groep1, 'groep2': nieuwe_groep2,
                            'score1': nieuwe_score1, 'score2': nieuwe_score2
                        }
        
        if beste_swap:
            return self._voer_speler_swap_uit(match1, match2, beste_swap)
        return False

    def _is_speler_swap_toegestaan(self, speler1: Dict, speler2: Dict, match1: Dict, match2: Dict) -> bool:
        """Check of speler swap toegestaan is"""
        return (self._zijn_alle_spelers_beschikbaar([speler1], match2['day'].capitalize(), match2['time'], match2['location']) and
                self._zijn_alle_spelers_beschikbaar([speler2], match1['day'].capitalize(), match1['time'], match1['location']))

    def _voer_speler_swap_uit(self, match1: Dict, match2: Dict, swap_info: Dict) -> bool:
        """Voer speler swap uit"""
        try:
            for i, match in enumerate(self.planning):
                if (match['week'] == match1['week'] and match['day'] == match1['day'] and
                    match['location'] == match1['location'] and match['time'] == match1['time'] and
                    match['baan'] == match1['baan']):
                    
                    groep = swap_info['groep1']
                    self.planning[i].update({
                        'group': ', '.join([f"{s['Voornaam']} {s['Achternaam']}" for s in groep]),
                        'speler_ids': [s['SpelerID'] for s in groep],
                       
                    })
                    break
            
            for i, match in enumerate(self.planning):
                if (match['week'] == match2['week'] and match['day'] == match2['day'] and
                    match['location'] == match2['location'] and match['time'] == match2['time'] and
                    match['baan'] == match2['baan']):
                    
                    groep = swap_info['groep2']
                    self.planning[i].update({
                        'group': ', '.join([f"{s['Voornaam']} {s['Achternaam']}" for s in groep]),
                        'speler_ids': [s['SpelerID'] for s in groep],
                        'quality_score': swap_info['score2']
                    })
                    break
            
            return True
        except:
            return False

    def _try_group_reassembly_for_week(self, poor_matches: List[Dict]) -> bool:
        """Probeer groep hersamenstelling"""
        if len(poor_matches) < 2:
            return False
        
        # Verzamel alle spelers en tijdslots
        all_players = []
        available_slots = []
        
        for match in poor_matches:
            all_players.extend(self._haal_spelers_uit_match(match))
            available_slots.append({
                'day': match['day'], 'location': match['location'], 
                'time': match['time'], 'baan': match['baan']
            })
        
        # Probeer nieuwe groepen te maken
        if len(all_players) >= 4:
            new_groups = self.optimize_groups_in_slot(all_players, len(available_slots))
            
            # Filter groepen met score > 0
            valid_groups = []
            for group in new_groups:
                score = self.calculate_group_quality_score(group)
                if score > 0.0:  # Alleen groepen die voldoen aan harde filters
                    valid_groups.append(group)
            
            if valid_groups:
                old_score = sum(m.get('quality_score', 0.0) for m in poor_matches)
                new_score = sum(self.calculate_group_quality_score(g) for g in valid_groups)
                
                if new_score > old_score + self.min_score_verbetering:
                    # Verwijder oude matches en voeg nieuwe toe
                    self.planning = [m for m in self.planning if m not in poor_matches]
                    
                    for i, group in enumerate(valid_groups[:len(available_slots)]):
                        slot = available_slots[i]
                        self.planning.append({
                            'week': poor_matches[0]['week'],
                            'day': slot['day'],
                            'location': slot['location'],
                            'time': slot['time'],
                            'baan': slot['baan'],
                            'group': ', '.join([f"{s['Voornaam']} {s['Achternaam']}" for s in group]),
                            'speler_ids': [s['SpelerID'] for s in group],
                            'group_size': 4,
                            'niveau': f"{min(int(float(s['Niveau'])) for s in group)}-{max(int(float(s['Niveau'])) for s in group)}",
                            'gender_balans': 'Hersamensteld',
                            'quality_score': self.calculate_group_quality_score(group),
                            'flexible_players': 0
                        })
                    
                    return True
        
        return False

    def export_planning_uitgebreid(self, planning_bestand, rapport_bestand):
        """Export planning en rapport"""
        with open(planning_bestand, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['week', 'day', 'location', 'time', 'baan', 'group_size', 'group', 'speler_ids', 'niveau', 'gender_balans', 'quality_score', 'legacy', 'legacy_type'])
            
            for match in self.planning:
                writer.writerow([
                    match['week'], match['day'], match['location'], match['time'], match['baan'],
                    match['group_size'], match['group'], ",".join(map(str, match['speler_ids'])),
                    match.get('niveau', ''), match.get('gender_balans', ''),
                    f"{match.get('quality_score', 0.0):.2f}",
                    match.get('legacy', False), match.get('legacy_type', '')
                ])
        
        with open(rapport_bestand, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['week', 'speler_id', 'naam', 'locatie_voorkeur', 'niveau'])
            
            for week_nummer, spelers in self.niet_ingeplande_spelers.items():
                for speler in spelers:
                    writer.writerow([
                        week_nummer, speler['SpelerID'], speler['Naam'],
                        speler['LocatieVoorkeur'], speler['Niveau']
                    ])
        
        print(f"Planning geëxporteerd naar: {planning_bestand}")
        print(f"Rapport geëxporteerd naar: {rapport_bestand}")

    def print_samenvatting(self):
        """Print samenvatting van de planning"""
        if not self.planning:
            print("Geen planning beschikbaar")
            return
        
        weken = set(match['week'] for match in self.planning)
        alle_scores = [match.get('quality_score', 0.0) for match in self.planning]
        gemiddelde_score = sum(alle_scores) / len(alle_scores) if alle_scores else 0.0
        
        print(f"\n=== HYBRIDE PLANNING SAMENVATTING ===")
        print(f"Aantal weken: {len(weken)}")
        print(f"Totaal aantal trainingen: {len(self.planning)}")
        print(f"Gemiddelde groepskwaliteit: {gemiddelde_score:.2f}")
        
        # Samenvatting per week
        for week in sorted(weken):
            week_matches = [m for m in self.planning if m['week'] == week]
            ingepland = len(self.ingeplande_spelers_per_week.get(week, set()))
            niet_ingepland = len(self.niet_ingeplande_spelers.get(week, []))
            
            week_scores = [m.get('quality_score', 0.0) for m in week_matches]
            week_gemiddelde = sum(week_scores) / len(week_scores) if week_scores else 0.0
            week_beste = max(week_scores) if week_scores else 0.0
            
            print(f"\nWeek {week}:")
            print(f"  - {len(week_matches)} trainingen")
            print(f"  - {ingepland} spelers ingepland")
            print(f"  - {niet_ingepland} spelers NIET ingepland")
            print(f"  - Kwaliteit: Ø{week_gemiddelde:.2f}, Best: {week_beste:.2f}")
            
            if niet_ingepland > 0:
                voorbeelden = [s['Naam'] for s in self.niet_ingeplande_spelers[week][:5]]
                extra = f" (en {niet_ingepland-5} anderen)" if niet_ingepland > 5 else ""
                print(f"    Niet ingepland: {', '.join(voorbeelden)}{extra}")
        
        # Top groepen
        print(f"\n=== KWALITEITSANALYSE ===")
        sorted_matches = sorted(self.planning, key=lambda x: x.get('quality_score', 0.0), reverse=True)
        
        print("Top 5 beste groepen:")
        for i, match in enumerate(sorted_matches[:5]):
            score = match.get('quality_score', 0.0)
            print(f"{i+1}. Week {match['week']}, {match['day']} {match['time']} - Score: {score:.2f}")
            print(f"   {match['group']} ({match.get('gender_balans', '')}, Niveau: {match.get('niveau', '')})")
        
        # Kwaliteitsverdeling
        score_ranges = {'Excellent (>9)': 0, 'Good (7-9)': 0, 'Average (5-7)': 0, 'Below Average (<5)': 0}
        for match in self.planning:
            score = match.get('quality_score', 0.0)
            if score > 9:
                score_ranges['Excellent (>9)'] += 1
            elif score >= 7:
                score_ranges['Good (7-9)'] += 1
            elif score >= 5:
                score_ranges['Average (5-7)'] += 1
            else:
                score_ranges['Below Average (<5)'] += 1
        
        print("\nKwaliteitsverdeling:")
        for range_name, count in score_ranges.items():
            percentage = (count / len(self.planning)) * 100 if self.planning else 0
            print(f"  {range_name}: {count} groepen ({percentage:.1f}%)")
        
        print("\n=== EIND SAMENVATTING ===")
        totaal_ingepland = sum(len(ids) for ids in self.ingeplande_spelers_per_week.values())
        totaal_niet_ingepland = sum(len(spelers) for spelers in self.niet_ingeplande_spelers.values())
        print(f"Totaal ingepland: {totaal_ingepland} spelers")
        print(f"Totaal niet ingepland: {totaal_niet_ingepland} spelers")
        print("===============================")

    def laad_legacy_groepen(self, bestand_pad):
        """Laad legacy groepen uit CSV bestand"""
        with open(bestand_pad, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            self.legacy_groepen = list(reader)
        
        print(f"Geladen: {len(self.legacy_groepen)} legacy groepen")
        return self.legacy_groepen
    
    def _vind_speler_by_naam(self, naam: str) -> Dict:
        """Vind speler object op basis van naam met flexibele matching"""
        naam_clean = self.normalize_name(naam)
        # Exacte match eerst proberen
        for speler in self.spelers:
            speler_naam = self.normalize_name(f"{speler['Voornaam']} {speler['Achternaam']}")
            if speler_naam == naam_clean:
                return speler
        # Flexibele match voor kleine verschillen
        for speler in self.spelers:
            speler_naam = self.normalize_name(f"{speler['Voornaam']} {speler['Achternaam']}")
            if speler_naam.replace(" ", "") == naam_clean.replace(" ", ""):
                return speler
        return None
    
    def _vind_best_passende_speler(self, beschikbare_spelers: List[Dict], bestaande_groep: List[Dict]) -> Dict:
        """Vind de best passende speler om toe te voegen aan een groep"""
        if not beschikbare_spelers or not bestaande_groep:
            return None
        
        # Bereken gemiddeld niveau en gender verdeling van bestaande groep
        niveaus = [float(s['Niveau']) for s in bestaande_groep if s['Niveau']]
        gemiddeld_niveau = sum(niveaus) / len(niveaus) if niveaus else 6.0
        
        mannen_count = sum(1 for s in bestaande_groep if s['Geslacht'] in ['M', 'Man', 'Jongen'])
        vrouwen_count = len(bestaande_groep) - mannen_count
        
        beste_kandidaat = None
        beste_score = -1
        
        for kandidaat in beschikbare_spelers:
            # Score op basis van niveau match
            try:
                kandidaat_niveau = float(kandidaat['Niveau'])
                niveau_verschil = abs(kandidaat_niveau - gemiddeld_niveau)
                niveau_score = max(0, 3 - niveau_verschil)  # Hoe kleiner verschil, hoe hoger score
            except:
                niveau_score = 0
            
            # Gender balans score
            is_man = kandidaat['Geslacht'] in ['M', 'Man', 'Jongen']
            gender_score = 0
            
            nieuwe_groep_size = len(bestaande_groep) + 1
            if nieuwe_groep_size == 4:  # Target grootte
                if (is_man and mannen_count < 2) or (not is_man and vrouwen_count < 2):
                    gender_score = 2  # Helpt met balans
                elif (is_man and mannen_count == 2) or (not is_man and vrouwen_count == 2):
                    gender_score = 1  # Homogene groep, ook ok
            
            totaal_score = niveau_score + gender_score
            
            if totaal_score > beste_score:
                beste_score = totaal_score
                beste_kandidaat = kandidaat
        
        return beste_kandidaat
    
    def _verwerk_legacy_groep(self, legacy_groep: Dict, week_nummer: int) -> bool:
        """Verwerk een legacy groep en plan deze in"""
        groep_id = legacy_groep.get('GroepID', 'Onbekend')
        speler_namen = [naam.strip() for naam in legacy_groep['Spelers'].split(',')]
        groep_spelers = []
        
        # Debug: toon welke groep we verwerken
        if week_nummer == 1:  # Alleen debug voor week 1 om output beheersbaar te houden
            print(f"    DEBUG: Verwerk groep {groep_id}")
            print(f"           Historische spelers: {speler_namen}")
        
        # Zoek alle spelers die in de legacy groep zitten EN willen blijven
        gevonden_spelers = []
        niet_gevonden_spelers = []
        willen_niet_blijven = []
        
        for naam in speler_namen:
            speler = self._vind_speler_by_naam(naam)
            if speler:
                gevonden_spelers.append(naam)
                if speler.get('BlijftInHuidigeGroep', '').lower() == 'ja':
                    groep_spelers.append(speler)
                else:
                    willen_niet_blijven.append(naam)
            else:
                niet_gevonden_spelers.append(naam)
        
        if week_nummer == 1:  # Debug output
            print(f"           Gevonden in aanmeldingen: {len(gevonden_spelers)} van {len(speler_namen)}")
            print(f"           Willen blijven: {len(groep_spelers)} spelers")
            if niet_gevonden_spelers:
                print(f"           NIET gevonden: {niet_gevonden_spelers[:3]}{'...' if len(niet_gevonden_spelers) > 3 else ''}")
            if willen_niet_blijven:
                print(f"           Willen NIET blijven: {willen_niet_blijven}")
        
        # NIEUWE LOGICA: Minimumgrootte van 2 afdwingen voor legacy groepen
        if len(groep_spelers) < 2:  
            if week_nummer == 1:
                print(f"           GEWEIGERD: Te weinig spelers willen blijven ({len(groep_spelers)} < 2)")
            return False
        
        # Haal de details van het oorspronkelijke slot vroeg op
        dag = legacy_groep['Dag']
        tijdslot = legacy_groep['Tijdslot']
        originele_locatie = legacy_groep['Locatie']

        # NIEUWE REGEL: Legacy groepen mogen alleen op hun originele locatie en tijd worden ingepland
        if week_nummer == 1:
            print(f"           NIEUWE REGEL: Legacy groep moet op originele locatie/tijd: {dag} {tijdslot} op {originele_locatie}")
        
        # Bepaal de doelgrootte - NIEUWE REGEL: alleen 4 spelers
        current_size = len(groep_spelers)
        target_size = 4  # Altijd 4 spelers volgens nieuwe harde filters
        
        if current_size < 4:
            if week_nummer == 1: print(f"           Legacy groep van {current_size}, probeer aan te vullen naar 4.")
        elif current_size > 4:
            # Als er meer dan 4 spelers zijn, houd alleen de eerste 4
            groep_spelers = groep_spelers[:4]
            if week_nummer == 1: print(f"           Legacy groep van {current_size} aangepast naar 4 spelers.")
        
        # Probeer groep aan te vullen naar gewenste grootte
        if len(groep_spelers) < target_size:
            # Vind beschikbare spelers die niet al ingepland zijn
            if week_nummer not in self.ingeplande_spelers_per_week:
                self.ingeplande_spelers_per_week[week_nummer] = set()
            
            ingeplande_ids = self.ingeplande_spelers_per_week[week_nummer]
            unplaced_players = [s for s in self.spelers if s['SpelerID'] not in ingeplande_ids and s['SpelerID'] not in [sp['SpelerID'] for sp in groep_spelers]]
            
            # Filter kandidaten op basis van beschikbaarheid voor het historische slot
            slot_candidates = [
                p for p in unplaced_players 
                if self._zijn_alle_spelers_beschikbaar([p], dag, tijdslot, originele_locatie)
            ]

            if week_nummer == 1:
                print(f"           Zoeken naar aanvulling voor {dag} {tijdslot} op {originele_locatie}.")
                print(f"           {len(slot_candidates)} van {len(unplaced_players)} niet-ingeplande spelers zijn beschikbaar.")

            # Voeg spelers toe tot target grootte uit de gefilterde kandidatenlijst
            aangevuld = 0
            while len(groep_spelers) < target_size and slot_candidates:
                beste_kandidaat = self._vind_best_passende_speler(slot_candidates, groep_spelers)
                if beste_kandidaat:
                    groep_spelers.append(beste_kandidaat)
                    slot_candidates.remove(beste_kandidaat)  # Verwijder uit kandidaten voor dit slot
                    unplaced_players.remove(beste_kandidaat) # Verwijder ook uit algemene pool voor deze iteratie
                    aangevuld += 1
                else:
                    break
            
            if week_nummer == 1:
                if aangevuld > 0:
                    print(f"           Aangevuld met {aangevuld} extra speler(s). Nieuwe grootte: {len(groep_spelers)}")
                elif len(groep_spelers) < target_size:
                    print(f"           WAARSCHUWING: Kon groep niet volledig aanvullen. Blijft een groep van {len(groep_spelers)}.")
        
        # Als groep te groot is, houd alleen de eerste target_size spelers
        if len(groep_spelers) > target_size:
            groep_spelers = groep_spelers[:target_size]
        
        # NIEUWE LOGICA: Check of alle spelers beschikbaar zijn op het originele tijdslot
        if week_nummer == 1:
            print(f"           Check beschikbaarheid op originele slot: {dag} {tijdslot} op {originele_locatie}")
        
        # Check of alle spelers beschikbaar zijn op dit tijdslot
        spelers_beschikbaar = self._zijn_alle_spelers_beschikbaar(groep_spelers, dag, tijdslot, originele_locatie)
        if week_nummer == 1:
            print(f"           Alle spelers beschikbaar op originele slot? {spelers_beschikbaar}")
            if not spelers_beschikbaar:
                # Debug welke spelers niet beschikbaar zijn
                for i, speler in enumerate(groep_spelers):
                    speler_tijden = self.parse_tijdslot(speler.get(dag, ''))
                    heeft_locatie = speler['LocatieVoorkeur'] == originele_locatie
                    heeft_voorkeuren = speler['SpelerID'] in self.samen_met_voorkeuren
                    
                    try:
                        tijdslot_start, tijdslot_eind = tijdslot.split('-')
                        tijd_overlap = any(self.tijden_overlappen((tijdslot_start, tijdslot_eind), (start, eind)) 
                                          for start, eind in speler_tijden)
                    except:
                        tijd_overlap = False
                    
                    locatie_ok = heeft_locatie or heeft_voorkeuren
                    
                    print(f"             {speler['Voornaam']} {speler['Achternaam']}: tijd_ok={tijd_overlap}, locatie_ok={locatie_ok}")
                    print(f"               Tijden {dag}: {speler.get(dag, 'Niet beschikbaar')}")
                    print(f"               LocatieVoorkeur: {speler['LocatieVoorkeur']}, heeft voorkeuren: {heeft_voorkeuren}")
        
        if not spelers_beschikbaar:
            if week_nummer == 1:
                print(f"           GEWEIGERD: Niet alle spelers beschikbaar op originele slot")
            return False
        
        # NIEUWE LOGICA: Check harde filters voor de groep
        if week_nummer == 1:
            print(f"           Check harde filters voor groep van {len(groep_spelers)} spelers")
        
        harde_filters_ok = self._voldoet_aan_harde_filters(groep_spelers, originele_locatie)
        if not harde_filters_ok:
            if week_nummer == 1:
                print(f"           GEWEIGERD: Groep voldoet niet aan harde filters")
            return False
        
        # Vind beschikbare baan op originele locatie
        baan_naam = self._vind_beschikbare_baan(week_nummer, dag, originele_locatie, tijdslot)
        if not baan_naam:
            if week_nummer == 1:
                print(f"           GEWEIGERD: Geen beschikbare baan op originele slot {dag} {tijdslot} op {originele_locatie}")
            return False
        
        # Alleen groepen van exact 4 spelers accepteren (nieuwe harde filter)
        if len(groep_spelers) != 4:
            if week_nummer == 1:
                print(f"           GEWEIGERD: Groepgrootte na aanvullen is {len(groep_spelers)} (alleen 4 toegestaan)")
            return False
        
        # Markeer spelers als ingepland
        for speler in groep_spelers:
            self.ingeplande_spelers_per_week[week_nummer].add(speler['SpelerID'])
        
        # Maak planning entry
        groep_namen = ', '.join([f"{s['Voornaam']} {s['Achternaam']}" for s in groep_spelers])
        
        # Bereken karakteristieken
        mannen_count = sum(1 for s in groep_spelers if s['Geslacht'] in ['M', 'Man', 'Jongen'])
        vrouwen_count = len(groep_spelers) - mannen_count
        
        if mannen_count == 2 and vrouwen_count == 2:
            gender_balans = 'Perfect (2M/2V)'
        elif mannen_count == len(groep_spelers):
            gender_balans = f'Homogeen ({mannen_count}M)'
        elif vrouwen_count == len(groep_spelers):
            gender_balans = f'Homogeen ({vrouwen_count}V)'
        else:
            gender_balans = f'Anders (M:{mannen_count}, V:{vrouwen_count})'
        
        niveaus = [float(s['Niveau']) for s in groep_spelers if s['Niveau']]
        if niveaus:
            if len(set(niveaus)) == 1:
                niveau = str(int(niveaus[0]))
            else:
                niveau = f"{int(min(niveaus))}-{int(max(niveaus))} (gemengd)"
        else:
            niveau = "Onbekend"
        
        # Bepaal het aantal blijvende spelers in de legacy groep
        legacy_info = self._bepaal_legacy_status(groep_spelers)
        # Bepaal of het een volledige legacy groep is (4 van 4 blijven)
        is_volledig_legacy = legacy_info['aantal_blijvend'] == legacy_info['totaal_origineel']
        
        # Bepaal de juiste legacy score
        if is_volledig_legacy:
            legacy_score = self.legacy_scoring['volledige_legacy_score']
        else:
            legacy_score = self._bereken_legacy_score(legacy_info)
        
        # Bepaal groep type
        if is_volledig_legacy:
            groep_type = "legacy_volledig"
        else:
            groep_type = "legacy_gedeeltelijk"
        
        match = {
            'week': week_nummer,
            'day': dag,
            'location': originele_locatie,
            'time': tijdslot,
            'baan': baan_naam,
            'group': groep_namen,
            'speler_ids': [s['SpelerID'] for s in groep_spelers],
            'group_size': len(groep_spelers),
            'niveau': niveau,
            'gender_balans': gender_balans,
            'quality_score': legacy_score,
            'flexible_players': 0,
            'legacy': True,
            'legacy_type': groep_type
        }
        
        self.planning.append(match)
        
        if week_nummer == 1:
            print(f"           GEACCEPTEERD: {groep_type} - {len(groep_spelers)} spelers op originele slot (score: {legacy_score})")
        
        return True
    
    def _vind_beschikbare_baan(self, week_nummer: int, dag: str, locatie: str, tijdslot: str) -> str:
        """Vind een beschikbare baan voor het opgegeven tijdslot"""
        for baan in self.banen:
            if (baan['Dag'] == dag and baan['Locatie'] == locatie and 
                baan['Tijdslot'] == tijdslot and 
                self._is_baan_beschikbaar(week_nummer, dag, locatie, tijdslot, baan['BaanNaam'])):
                return baan['BaanNaam']
        return None
    
    def _vind_alternatief_legacy_slot(self, groep_spelers: List[Dict], voorkeur_dag: str, voorkeur_locatie: str) -> Dict:
        """Vind alternatief tijdslot voor legacy groep"""
        # Probeer eerst zelfde dag, andere tijden
        dag_banen = [b for b in self.banen if b['Dag'] == voorkeur_dag and b['Locatie'] == voorkeur_locatie]
        
        for baan in dag_banen:
            if self._zijn_alle_spelers_beschikbaar(groep_spelers, voorkeur_dag, baan['Tijdslot'], voorkeur_locatie):
                return {'tijdslot': baan['Tijdslot'], 'baan': baan['BaanNaam']}
        
        # Probeer andere dagen, zelfde locatie
        andere_banen = [b for b in self.banen if b['Locatie'] == voorkeur_locatie]
        
        for baan in andere_banen:
            if self._zijn_alle_spelers_beschikbaar(groep_spelers, baan['Dag'], baan['Tijdslot'], voorkeur_locatie):
                return {'tijdslot': baan['Tijdslot'], 'baan': baan['BaanNaam']}
        
        return None
    
    def plan_legacy_groepen(self, aantal_weken: int = 12):
        """Plan alle legacy groepen in voor alle weken"""
        print("=== FASE 0: LEGACY GROEPEN PLANNING ===")
        
        legacy_gepland = 0
        legacy_mislukt = 0
        
        for week_nummer in range(1, aantal_weken + 1):
            if week_nummer not in self.ingeplande_spelers_per_week:
                self.ingeplande_spelers_per_week[week_nummer] = set()
            
            week_legacy_count = 0
            for legacy_groep in self.legacy_groepen:
                if self._verwerk_legacy_groep(legacy_groep, week_nummer):
                    week_legacy_count += 1
                    legacy_gepland += 1
                else:
                    legacy_mislukt += 1
            
            print(f"  Week {week_nummer}: {week_legacy_count} legacy groepen ingepland")
        
        print(f"Legacy groepen planning voltooid:")
        print(f"  - {legacy_gepland} legacy groepen succesvol ingepland")
        print(f"  - {legacy_mislukt} legacy groepen konden niet worden ingepland")
        print(f"  - Totaal: {len(self.planning)} legacy trainingen")

    def normalize_name(self, name: str) -> str:
        """Normaliseer naam: lowercase, verwijder accenten/umlauts, verwijder spaties"""
        if not name:
            return ''
        # Unicode normalisatie (NFKD), verwijder accenten
        name = unicodedata.normalize('NFKD', name)
        name = ''.join([c for c in name if not unicodedata.combining(c)])
        # Lowercase en verwijder spaties
        return name.lower().replace(' ', '')

if __name__ == '__main__':
    # Initialiseer algoritme
    algoritme = HybridPlanningAlgorithm()
    
    # AANGEPAST: Gebruik de beschikbare dataset en laad legacy groepen
    print("=== PLANNING MET LEGACY GROEPEN ONDERSTEUNING ===")
    algoritme.laad_spelers('../data/Spelers_aanmeldingen.csv')
    algoritme.laad_banen('../data/Herziende dataverzameling - BaanBeschikbaarheid.csv')
    algoritme.laad_legacy_groepen('../data/Historische_Groepen.csv')
    
    # Maak planning voor 12 weken (3 maanden)
    planning = algoritme.maak_planning_meerdere_weken(aantal_weken=12)
    
    # Export naar bestanden
    algoritme.export_planning_uitgebreid(
        '../planning/trainingsindeling.csv', 
        '../planning/niet_ingeplande_spelers.csv'
    )
    
    # Print samenvatting
    algoritme.print_samenvatting()