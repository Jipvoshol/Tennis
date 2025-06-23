#!/usr/bin/env python3

import json
from planning_algorithm import HybridPlanningAlgorithm

def test_specific_group():
    """Test score berekening voor specifieke groep"""
    
    # Initialiseer algoritme
    algoritme = HybridPlanningAlgorithm()
    algoritme.laad_spelers('../data/Spelers_aanmeldingen.csv')
    
    # Test groepen
    test_groepen = [
        # Groep 1: Jeroen Glebbeek, Daan Van Apeldoorn, Noud Gabel, Emile Röell (score: 9.17)
        {
            'namen': ['Jeroen Glebbeek', 'Daan Van Apeldoorn', 'Noud Gabel', 'Emile Röell'],
            'ids': ['71', '101', '69', '103'],
            'locatie': 'Joy Jaagpad'
        },
        # Groep 2: Lotte Bruinink, Jovanna Koens, Merel Vrolijk, Sanne van Amerongen (score: 10.00)
        {
            'namen': ['Lotte Bruinink', 'Jovanna Koens', 'Merel Vrolijk', 'Sanne van Amerongen'],
            'ids': ['42', '68', '40', '93'],
            'locatie': 'Joy Jaagpad'
        },
        # Groep 3: Tessa Schop, Rianne de Wit, Kristin Wahle, Madeleine Versteeg (score: 5.00)
        {
            'namen': ['Tessa Schop', 'Rianne de Wit', 'Kristin Wahle', 'Madeleine Versteeg'],
            'ids': ['45', '46', '48', '112'],
            'locatie': 'Joy Jaagpad'
        }
    ]
    
    for i, groep_info in enumerate(test_groepen, 1):
        print(f"\n{'='*60}")
        print(f"GROEP {i}: {', '.join(groep_info['namen'])}")
        print(f"{'='*60}")
        
        # Maak test groep
        test_groep = []
        for speler in algoritme.spelers:
            if speler['SpelerID'] in groep_info['ids']:
                test_groep.append(speler)
        
        # Toon speler details
        for speler in test_groep:
            print(f"  {speler['Voornaam']} {speler['Achternaam']}:")
            print(f"    Niveau: {speler['Niveau']}")
            print(f"    Geslacht: {speler['Geslacht']}")
            print(f"    Leeftijd: {speler.get('Leeftijd', 'Onbekend')}")
            print(f"    LocatieVoorkeur: {speler['LocatieVoorkeur']}")
            print(f"    SamenMet: {speler.get('SamenMet', 'Geen')}")
            print(f"    BlijftInHuidigeGroep: {speler.get('BlijftInHuidigeGroep', 'Geen')}")
        
        # Bereken totale score
        totale_score = algoritme.calculate_group_quality_score(test_groep, groep_info['locatie'])
        print(f"\nTotale score: {totale_score}")
        
        # Bereken individuele componenten
        scoring = algoritme.config['nieuwe_groep_scoring']
        
        # 1. Niveau homogeniteit
        niveau_score = algoritme._bereken_niveau_score(test_groep, scoring['niveau_homogeniteit'])
        print(f"Niveau homogeniteit score: {niveau_score}")
        
        # 2. Samen-met voorkeur
        samen_met_score = algoritme._bereken_samen_met_score(test_groep, scoring['samen_met_voorkeur'])
        print(f"Samen-met voorkeur score: {samen_met_score}")
        
        # 3. Geslachtsbalans
        geslacht_score = algoritme._bereken_geslacht_score(test_groep, scoring['geslachtsbalans'])
        print(f"Geslachtsbalans score: {geslacht_score}")
        
        # 4. Leeftijdsmatch
        leeftijd_score = algoritme._bereken_leeftijd_score(test_groep, scoring['leeftijdsmatch'])
        print(f"Leeftijdsmatch score: {leeftijd_score}")
        
        # Controleer harde filters
        harde_filters_ok = algoritme._voldoet_aan_harde_filters(test_groep, groep_info['locatie'])
        print(f"\nHarde filters OK: {harde_filters_ok}")
        
        # Toon niveau verdeling
        niveaus = [float(s['Niveau']) for s in test_groep if s['Niveau']]
        print(f"Niveaus: {niveaus}")
        print(f"Niveau verschil: {max(niveaus) - min(niveaus)}")
        
        # Toon gender verdeling
        mannen = sum(1 for s in test_groep if s['Geslacht'] in ['M', 'Man', 'Jongen'])
        vrouwen = len(test_groep) - mannen
        print(f"Gender verdeling: {mannen}M, {vrouwen}V")
        
        # Toon leeftijden
        leeftijden = []
        for speler in test_groep:
            try:
                leeftijd = int(speler.get('Leeftijd', ''))
                leeftijden.append(leeftijd)
            except (ValueError, TypeError):
                continue
        print(f"Leeftijden: {leeftijden}")
        
        # Toon SamenMet matches
        print(f"\nSamenMet analyse:")
        groep_namen = set()
        for speler in test_groep:
            voornaam = (speler.get('Voornaam', '') or '').strip()
            achternaam = (speler.get('Achternaam', '') or '').strip()
            if voornaam and achternaam:
                groep_namen.add(f"{voornaam} {achternaam}".lower())
        
        wederzijdse_paren = 0
        for speler in test_groep:
            if speler['SpelerID'] in algoritme.samen_met_voorkeuren:
                for partner_naam in algoritme.samen_met_voorkeuren[speler['SpelerID']]:
                    if partner_naam in groep_namen:
                        speler_naam = f"{speler['Voornaam']} {speler['Achternaam']}".lower()
                        partner_id = algoritme.speler_naam_naar_id.get(partner_naam)
                        if (partner_id and partner_id in algoritme.samen_met_voorkeuren and 
                            speler_naam in algoritme.samen_met_voorkeuren[partner_id]):
                            wederzijdse_paren += 1
                            print(f"  Wederzijds paar: {speler['Voornaam']} <-> {partner_naam}")
        
        wederzijdse_paren //= 2  # Delen door 2 omdat elk paar dubbel geteld wordt
        print(f"  Totaal wederzijdse paren: {wederzijdse_paren}")

def test_wederzijdse_voorkeuren():
    """Test wederzijdse voorkeuren in een specifieke groep"""
    
    # Initialiseer algoritme
    algoritme = HybridPlanningAlgorithm()
    algoritme.laad_spelers('../data/Spelers_aanmeldingen_UPDATED.csv')
    
    # Test groep: "Jeroen Glebbeek, Daan Van Apeldoorn, Noud Gabel, Emile Röell"
    test_groep = []
    groep_namen = ["Jeroen Glebbeek", "Daan Van Apeldoorn", "Noud Gabel", "Emile Röell"]
    
    print("=== WEDERZIJDSE VOORKEUREN ANALYSE ===")
    print(f"Test groep: {', '.join(groep_namen)}")
    print()
    
    # Zoek spelers en toon hun voorkeuren
    for naam in groep_namen:
        speler = None
        for s in algoritme.spelers:
            speler_naam = f"{s['Voornaam']} {s['Achternaam']}".strip()
            if speler_naam.lower() == naam.lower():
                speler = s
                break
        
        if speler:
            test_groep.append(speler)
            print(f"Speler: {speler['Voornaam']} {speler['Achternaam']} (ID: {speler['SpelerID']})")
            print(f"  SamenMet voorkeuren: {speler.get('SamenMet', 'Geen')}")
            
            # Check of speler voorkeuren heeft in de algoritme mapping
            if speler['SpelerID'] in algoritme.samen_met_voorkeuren:
                voorkeuren = algoritme.samen_met_voorkeuren[speler['SpelerID']]
                print(f"  Geparseerde voorkeuren: {list(voorkeuren)}")
            else:
                print(f"  Geen voorkeuren gevonden in mapping")
            print()
        else:
            print(f"Speler niet gevonden: {naam}")
            print()
    
    if len(test_groep) == 4:
        print("=== WEDERZIJDSE PAREN ANALYSE ===")
        
        # Check alle mogelijke paren
        wederzijdse_paren = []
        groep_ids = {s['SpelerID'] for s in test_groep}
        
        for speler in test_groep:
            speler_id = speler['SpelerID']
            speler_naam = f"{speler['Voornaam']} {speler['Achternaam']}"
            
            if speler_id in algoritme.samen_met_voorkeuren:
                for partner_naam in algoritme.samen_met_voorkeuren[speler_id]:
                    partner_id = algoritme.speler_naam_naar_id.get(partner_naam)
                    if partner_id and partner_id in groep_ids:
                        # Check wederkerigheid
                        if (partner_id in algoritme.samen_met_voorkeuren and 
                            speler_id in algoritme.samen_met_voorkeuren[partner_id]):
                            wederzijdse_paren.append((speler_naam, partner_naam))
                            print(f"✓ Wederzijds paar gevonden: {speler_naam} ↔ {partner_naam}")
                        else:
                            print(f"✗ Eenrichtings voorkeur: {speler_naam} → {partner_naam}")
        
        print(f"\nTotaal wederzijdse paren: {len(wederzijdse_paren)}")
        
        # Bereken score volgens configuratie
        scoring_config = algoritme.config['nieuwe_groep_scoring']['samen_met_voorkeur']
        if len(wederzijdse_paren) >= 3:
            score = scoring_config['scores']['3_plus_paren']
        elif len(wederzijdse_paren) == 2:
            score = scoring_config['scores']['2_paren']
        elif len(wederzijdse_paren) == 1:
            score = scoring_config['scores']['1_paar']
        else:
            score = 0.0
        
        print(f"Berekende samen-met score: {score}")
        
        # Test de volledige score berekening
        print("\n=== VOLLEDIGE SCORE BEREKENING ===")
        totaal_score = algoritme.calculate_group_quality_score(test_groep)
        print(f"Totaal score: {totaal_score}")
        
        # Debug de individuele componenten
        print("\n=== INDIVIDUELE COMPONENTEN ===")
        
        # Niveau score
        niveau_score = algoritme._bereken_niveau_score(test_groep, algoritme.config['nieuwe_groep_scoring']['niveau_homogeniteit'])
        print(f"Niveau homogeniteit: {niveau_score}")
        
        # Samen-met score
        samen_met_score = algoritme._bereken_samen_met_score(test_groep, algoritme.config['nieuwe_groep_scoring']['samen_met_voorkeur'])
        print(f"Samen-met voorkeur: {samen_met_score}")
        
        # Geslacht score
        geslacht_score = algoritme._bereken_geslacht_score(test_groep, algoritme.config['nieuwe_groep_scoring']['geslachtsbalans'])
        print(f"Geslachtsbalans: {geslacht_score}")
        
        # Leeftijd score
        leeftijd_score = algoritme._bereken_leeftijd_score(test_groep, algoritme.config['nieuwe_groep_scoring']['leeftijdsmatch'])
        print(f"Leeftijdsmatch: {leeftijd_score}")
        
        # Harde filters
        harde_filters_ok = algoritme._voldoet_aan_harde_filters(test_groep)
        print(f"Harde filters voldaan: {harde_filters_ok}")
        
        # Toon niveau verdeling
        niveaus = [float(s['Niveau']) for s in test_groep if s['Niveau']]
        print(f"Niveaus in groep: {niveaus}")
        print(f"Niveau verschil: {max(niveaus) - min(niveaus) if niveaus else 'N/A'}")
        
        # Toon geslacht verdeling
        mannen = sum(1 for s in test_groep if s['Geslacht'] in ['M', 'Man', 'Jongen'])
        vrouwen = len(test_groep) - mannen
        print(f"Geslacht verdeling: {mannen}M, {vrouwen}V")

def debug_naam_matching():
    """Debug naam matching problemen"""
    
    # Initialiseer algoritme
    algoritme = HybridPlanningAlgorithm()
    algoritme.laad_spelers('../data/Spelers_aanmeldingen_UPDATED.csv')
    
    print("=== NAAM MATCHING DEBUG ===")
    
    # Test specifieke spelers
    test_spelers = [
        ("Daan Van Apeldoorn", "Emile Röell"),
        ("Emile Röell", "Daan Van Apeldoorn")
    ]
    
    for speler_naam, partner_naam in test_spelers:
        print(f"\nTest: {speler_naam} → {partner_naam}")
        
        # Zoek speler
        speler = None
        for s in algoritme.spelers:
            speler_naam_full = f"{s['Voornaam']} {s['Achternaam']}".strip()
            if speler_naam_full.lower() == speler_naam.lower():
                speler = s
                break
        
        if not speler:
            print(f"  ❌ Speler niet gevonden: {speler_naam}")
            continue
        
        print(f"  ✅ Speler gevonden: {speler['Voornaam']} {speler['Achternaam']} (ID: {speler['SpelerID']})")
        print(f"  📝 Originele SamenMet: '{speler.get('SamenMet', '')}'")
        
        # Check geparseerde voorkeuren
        if speler['SpelerID'] in algoritme.samen_met_voorkeuren:
            voorkeuren = algoritme.samen_met_voorkeuren[speler['SpelerID']]
            print(f"  🔍 Geparseerde voorkeuren: {list(voorkeuren)}")
            
            # Check of partner in voorkeuren staat
            partner_lower = partner_naam.lower()
            if partner_lower in voorkeuren:
                print(f"  ✅ Partner '{partner_naam}' gevonden in voorkeuren")
                
                # Check of partner bestaat in naam mapping
                if partner_lower in algoritme.speler_naam_naar_id:
                    partner_id = algoritme.speler_naam_naar_id[partner_lower]
                    print(f"  ✅ Partner ID gevonden: {partner_id}")
                    
                    # Check of partner ook voorkeuren heeft
                    if partner_id in algoritme.samen_met_voorkeuren:
                        partner_voorkeuren = algoritme.samen_met_voorkeuren[partner_id]
                        print(f"  🔍 Partner voorkeuren: {list(partner_voorkeuren)}")
                        
                        # Check wederkerigheid
                        speler_naam_lower = speler_naam.lower()
                        if speler_naam_lower in partner_voorkeuren:
                            print(f"  ✅ WEDERZIJDSE VOORKEUR GEVONDEN!")
                        else:
                            print(f"  ❌ Geen wederzijdse voorkeur (zoekt naar: '{speler_naam_lower}')")
                    else:
                        print(f"  ❌ Partner heeft geen voorkeuren")
                else:
                    print(f"  ❌ Partner niet gevonden in naam mapping")
                    print(f"  🔍 Beschikbare namen in mapping (eerste 10): {list(algoritme.speler_naam_naar_id.keys())[:10]}")
            else:
                print(f"  ❌ Partner '{partner_naam}' niet gevonden in voorkeuren")
                print(f"  🔍 Zoekt naar: '{partner_lower}'")
        else:
            print(f"  ❌ Speler heeft geen voorkeuren")
    
    print("\n=== NAAM MAPPING ANALYSE ===")
    print(f"Totaal namen in mapping: {len(algoritme.speler_naam_naar_id)}")
    
    # Zoek naar vergelijkbare namen
    print("\nZoeken naar 'emile' en 'daan' in mapping:")
    for naam, speler_id in algoritme.speler_naam_naar_id.items():
        if 'emile' in naam or 'daan' in naam:
            print(f"  {naam} -> {speler_id}")

if __name__ == "__main__":
    test_specific_group()
    test_wederzijdse_voorkeuren()
    debug_naam_matching() 