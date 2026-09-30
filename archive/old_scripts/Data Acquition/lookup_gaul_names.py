"""
Query FAO GAUL Level 2 to find correct district names for missing areas.
This script searches GAUL for the regions we need but couldn't match.
"""
import ee

PROJECT_ID = 'vernal-parser-412016'
ee.Initialize(project=PROJECT_ID)

gaul2 = ee.FeatureCollection("FAO/GAUL/2015/level2")

# =============================================================================
# 1. SOUTH AFRICA — Find all ADM2 names in Limpopo Province
#    We need: Musina, Mutale, Thohoyandou (these are local municipal names)
# =============================================================================
print("=" * 70)
print("SOUTH AFRICA — All ADM2 names (looking for Limpopo/Vhembe region)")
print("=" * 70)

sa_all = gaul2.filter(ee.Filter.eq('ADM0_NAME', 'South Africa'))
sa_names = sa_all.aggregate_array('ADM2_NAME').distinct().sort().getInfo()
print(f"\nAll South Africa ADM2 names ({len(sa_names)} total):")
for n in sa_names:
    print(f"  {n}")

# Also check ADM1 names to understand province structure
sa_adm1 = sa_all.aggregate_array('ADM1_NAME').distinct().sort().getInfo()
print(f"\nSouth Africa ADM1 (Province) names:")
for n in sa_adm1:
    print(f"  {n}")

# Filter to Limpopo specifically
sa_limpopo = sa_all.filter(ee.Filter.eq('ADM1_NAME', 'Limpopo'))
limpopo_names = sa_limpopo.aggregate_array('ADM2_NAME').distinct().sort().getInfo()
print(f"\nLimpopo Province ADM2 names:")
for n in limpopo_names:
    print(f"  {n}")

# =============================================================================
# 2. MOZAMBIQUE — Search for Beira, Inhambane, Quelimane, Vilanculo, Maganja
# =============================================================================
print(f"\n{'=' * 70}")
print("MOZAMBIQUE — Searching for missing district names")
print("=" * 70)

moz_all = gaul2.filter(ee.Filter.eq('ADM0_NAME', 'Mozambique'))
moz_names = moz_all.aggregate_array('ADM2_NAME').distinct().sort().getInfo()
print(f"\nAll Mozambique ADM2 names ({len(moz_names)} total):")
for n in moz_names:
    print(f"  {n}")

# Search for partial matches
search_terms = ['beira', 'inhambane', 'quelimane', 'vilanculo', 'vilankulo', 'maganja']
print(f"\nSearching for partial matches:")
for term in search_terms:
    matches = [n for n in moz_names if term.lower() in n.lower()]
    print(f"  '{term}' -> {matches}")

# =============================================================================
# 3. MADAGASCAR — Search for Ambato-Boeni, Antananarivo Renivohitra, 
#    Mahajanga Ii, Manakara
# =============================================================================
print(f"\n{'=' * 70}")
print("MADAGASCAR — Searching for missing district names")
print("=" * 70)

mad_all = gaul2.filter(ee.Filter.eq('ADM0_NAME', 'Madagascar'))
mad_names = mad_all.aggregate_array('ADM2_NAME').distinct().sort().getInfo()
print(f"\nAll Madagascar ADM2 names ({len(mad_names)} total):")
for n in mad_names:
    print(f"  {n}")

search_terms_mad = ['ambato', 'renivohitra', 'mahajanga', 'manakara']
print(f"\nSearching for partial matches:")
for term in search_terms_mad:
    matches = [n for n in mad_names if term.lower() in n.lower()]
    print(f"  '{term}' -> {matches}")

# =============================================================================
# 4. ZIMBABWE — Search for Mutare variants
# =============================================================================
print(f"\n{'=' * 70}")
print("ZIMBABWE — Searching for Mutare variants")
print("=" * 70)

zim_all = gaul2.filter(ee.Filter.eq('ADM0_NAME', 'Zimbabwe'))
zim_names = zim_all.aggregate_array('ADM2_NAME').distinct().sort().getInfo()
print(f"\nAll Zimbabwe ADM2 names ({len(zim_names)} total):")
for n in zim_names:
    print(f"  {n}")

search_terms_zim = ['mutare', 'manicaland']
print(f"\nSearching for partial matches:")
for term in search_terms_zim:
    matches = [n for n in zim_names if term.lower() in n.lower()]
    print(f"  '{term}' -> {matches}")

print(f"\n{'=' * 70}")
print("DONE — Use results above to fix district names in Test_data.py")
print("=" * 70)
