import pandas as pd
import pandapower as pp
import pandapower.plotting as plot

file_load = r"C:\Users\Noah\Desktop\EE TH Köln\Semester 2\Stromnetze\Daten\OneDrive_1_14.6.2026\Lastprofile.xlsx"
file_lines = r"C:\Users\Noah\Desktop\EE TH Köln\Semester 2\Stromnetze\Daten\Stromnetze_Auslegungsdaten - Kopie.xlsx"

Verbrauch_Haushalt = pd.read_excel(file_load, header=[0,1], index_col=[0,1],skiprows=1)
lines = pd.read_excel(file_lines, index_col=0)
lines = lines.rename(columns={"Länge": "Laenge"})

#print(Verbrauch_Haushalt)
#print(lines)
#create modell
n = pp.create_empty_network()
#create buses
b1 = pp.create_bus(n, vn_kv=20., name="Bus 1", type="b")
b2 = pp.create_bus(n, vn_kv=0.4, name="Bus LV0", type="b")
#Transformator 20kv / 1.0kv
trafo1 = pp.create_transformer(n, hv_bus=b1, lv_bus=b2, std_type="0.4 MVA 20/0.4 kV", name="Trafo")
#Abhaenge LV Netz von links nach rechts aufbauen
buses = {}
def extraction(df, Kabelnummer: int):
    df = df.loc[[Kabelnummer]]
    for i in range(len(df)):
        buses[f"Bus_LV{Kabelnummer}.{i}"] = pp.create_bus(n, name=f"busLV{Kabelnummer}.{i}", vn_kv=0.4, type="n")
    return n

def Line_erstellen(df, Kabelnummer: int):
    #df = df.sort_index()
    #neuer Index mit Zählung enumerate und row als Tuple der Zeile
    for i, row in enumerate(df.itertuples()):
        if i == 0:
            # Erste Leitung eines geraden Kabelnummernblocks startet am LV-Bus b2 und geht auf Kabelnummer.0
            from_bus = b2
            to_bus = buses[f"Bus_LV{Kabelnummer}.{i}"]
        #ansonsten startet der Bus bei Kabelenummer.0 und verbindet sich mit 2.1
        else:
            from_bus = buses[f"Bus_LV{Kabelnummer}.{i-1}"]
            to_bus = buses[f"Bus_LV{Kabelnummer}.{i}"]
        typ = row.Leitungstyp

        if typ not in n.std_types["line"]:
            typ = "NAYY 4x150 SE"

        laenge_km = row.Laenge / 1000
        pp.create_line(n, from_bus=from_bus,
                       to_bus=to_bus, length_km=laenge_km,
                       std_type=typ, #Kabeltyp muss noch definiert werden
                       name=f"Kabel_{Kabelnummer}_{i}")
    return n

pp.create_ext_grid(n, bus=b1, vm_pu=1.02, name="grid_connection")
for l, group in lines.groupby(level=0):
    extraction(group, l)
    Line_erstellen(group,l)
#Lastprofile aufbauen
lastprofile = {"Haushalt_1":Verbrauch_Haushalt[1],
                  "Haushalt_2":Verbrauch_Haushalt[2],
                  "Haushalt_3":Verbrauch_Haushalt[3],
                  "Haushalt_4":Verbrauch_Haushalt[4]
}
print(lastprofile)
#Lasten einfügen an die Buses

pp.create_load(n,bus=11,p_mw=Verbrauch_Haushalt[1])
print(n.bus)
#print(n.trafo)
print(n.line)
print(n.load)

#pp.runpp(n)