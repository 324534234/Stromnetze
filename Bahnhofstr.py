import pandas as pd
import pandapower as pp
from pandapower.timeseries import DFData, OutputWriter, run_timeseries
from pandapower.control import ConstControl
from demandlib import bdew #für Standardlastprofile          
import os

file_load = "Lastprofile.xlsx"
file_lines = "Stromnetze_Auslegungsdaten - Kopie.xlsx"

lines = pd.read_excel(file_lines, index_col=0)
lines = lines.rename(columns={"Länge": "Laenge"})

#Erstellen der Standardlastprofile
slp = bdew.ElecSlp(2021)

baecker_slp = slp.get_scaled_power_profiles({"g5": 25000}).resample("h").mean()
restaurant_slp = slp.get_scaled_power_profiles({"g2": 45000}).resample("h").mean()
edeka_slp = slp.get_scaled_power_profiles({"g4": 130000}).resample("h").mean()
doner_slp = slp.get_scaled_power_profiles({"g4": 15000}).resample("h").mean()
Elektroladen_slp = slp.get_scaled_power_profiles({"g4": 15000}).resample("h").mean()
Handwerkladen_slp = slp.get_scaled_power_profiles({"g3": 105000}).resample("h").mean()

#create modell
def build_network(lines):
    n = pp.create_empty_network()
    #create buses
    b1 = pp.create_bus(n, vn_kv=20., name="Bus 1", type="b")
    b2 = pp.create_bus(n, vn_kv=0.4, name="Bus LV0", type="b")
    #Transformator 20kv / 1.0kv
    pp.create_transformer(n, hv_bus=b1, lv_bus=b2, std_type="0.4 MVA 20/0.4 kV", name="Trafo")
    pp.create_ext_grid(n, bus=b1, vm_pu=1.00, name="grid_connection")
    #Abhaenge LV Netz von links nach rechts aufbauen
    buses = {}

    def extraction(df, Kabelnummer: int):
        for i in range(len(df)):
            buses[f"Bus_LV{Kabelnummer}.{i}"] = pp.create_bus(n, name=f"busLV{Kabelnummer}.{i}", vn_kv=0.4, type="n")
        return n

    def line_erstellen(df, Kabelnummer: int):
        #neuer Index mit Zählung enumerate und row als Tuple der Zeile
        for i, row in enumerate(df.itertuples()):
            if i == 0:
                # Erste Leitung eines geraden Kabelnummernblocks startet am LV-Bus b2 und geht auf Kabelnummer.0
                from_bus = abzweig_start.get(Kabelnummer, b2)
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
                        std_type=typ, 
                        name=f"Kabel_{Kabelnummer}_{i}")
        

    for l, group in lines.groupby(level=0):
        extraction(group, l)

    abzweig_start = {
        111: buses["Bus_LV11.0"],  
    }
    
    for l, group in lines.groupby(level=0):
        line_erstellen(group, l)

    bus_info = []
    for l, group in lines.groupby(level=0):
        for i, row in enumerate(group.itertuples()):
            bus_name = f"busLV{l}.{i}"
            bus_idx = n.bus[n.bus['name'] == bus_name].index[0]
            bus_info.append({"index": bus_idx, "name": bus_name, "endpunkt": row.Endpunkt,
                            "strang": l})  
    bus_info_df = pd.DataFrame(bus_info)  
    return n, bus_info_df



#Umbennen der Columnsudn anschließend einfügen an die Buses
lastprofile = {
    1:"Haushalt_1",
    2:"Haushalt_2",
    3:"Haushalt_3",
    4:"Haushalt_4",
    5:"Haushalt_5",
    6:"Haushalt_6"
}

# Mapping von Haushaltsnamen auf Busindizes.
load_bus_mapping = {
    "Haushalt_1": 3,      # BHS 35       
    "Haushalt_2": 7,      # BHS 36      
    "Haushalt_3": 25,     # BHS 27a     
    "Haushalt_4": 19,     # BHS 25    
    "Haushalt_5": 20,     # BHS 23       
    "Haushalt_6": 21,     # BHS 21      
    "baecker": 24,        # BHS 27     
    "restaurant": 9,      # BHS 38       
    "edeka1": 14,         # EDEKA 
    "edeka2": 15,         # EDEKA  
    "edeka3": 16,         # EDEKA    
    "edeka4": 17,         # EDEKA  
    "doner": 5,           # BHS 32       
    "Elektroladen": 6,    # BHS 34       
    "Handwerkladen": 8,   # BHS 36a      
}

pv_istzustand = {
    "pv_Haushalt_2":    {"file": "PV/ninja_pv_istzustand_BHS36.xlsx",    "bus": 7,  "kwpeak": 0.6},
    "pv_edeka1":        {"file": "PV/ninja_pv_istzustand_BHS29-33.xlsx", "bus": 14, "kwpeak": 170.03/4},
    "pv_edeka2":        {"file": "PV/ninja_pv_istzustand_BHS29-33.xlsx", "bus": 15, "kwpeak": 170.03/4},
    "pv_edeka3":        {"file": "PV/ninja_pv_istzustand_BHS29-33.xlsx", "bus": 16, "kwpeak": 170.03/4},
    "pv_edeka4":        {"file": "PV/ninja_pv_istzustand_BHS29-33.xlsx", "bus": 17, "kwpeak": 170.03/4},
    "pv_Handwerkladen": {"file": "PV/ninja_pv_istzustand_BHS36a.xlsx",   "bus": 8,  "kwpeak": 27},
}

pv_geplant = {
    "pv_Haushalt_1":      {"file": "PV/ninja_pv_BHS35.xlsx",       "bus": 3,  "kwpeak": 24.66},
    "pv_Haushalt_3_ost":  {"file": "PV/ninja_pv_BHS27a_Ost.xlsx",  "bus": 25, "kwpeak": 19.06},
    "pv_Haushalt_3_west": {"file": "PV/ninja_pv_BHS27a_West.xlsx", "bus": 25, "kwpeak": 19.06},
    "pv_Haushalt_4_süd":  {"file": "PV/ninja_pv_BHS25_süd.xlsx",   "bus": 19, "kwpeak": 10.75},
    "pv_Haushalt_4_nord": {"file": "PV/ninja_pv_BHS25_nord.xlsx",  "bus": 19, "kwpeak": 10.75},
    "pv_baecker_ost":     {"file": "PV/ninja_pv_BHS27_Ost.xlsx",   "bus": 24, "kwpeak": 39.89},
    "pv_baecker_west":    {"file": "PV/ninja_pv_BHS27_West.xlsx",  "bus": 24, "kwpeak": 39.89},
    "pv_restaurant_nord": {"file": "PV/ninja_pv_BHS38_Nord.xlsx",  "bus": 9,  "kwpeak": 23.52},  
    "pv_restaurant_süd":  {"file": "PV/ninja_pv_BHS38_Süd.xlsx",   "bus": 9,  "kwpeak": 22.89},
    "pv_doner_ost":       {"file": "PV/ninja_pv_BHS32_Ost.xlsx",   "bus": 5,  "kwpeak": 56.01/2},
    "pv_doner_west":      {"file": "PV/ninja_pv_BHS32_West.xlsx",  "bus": 5,  "kwpeak": 56.01/2},
    "pv_Elektroladen":    {"file": "PV/ninja_pv_BHS34.xlsx",       "bus": 6,  "kwpeak": 42.64}, 
    "pv_Haushalt_6_ost":  {"file": "PV/ninja_pv_BHS21_ost.xlsx",   "bus": 21, "kwpeak": 14.46},
    "pv_Haushalt_6_west": {"file": "PV/ninja_pv_BHS21_west.xlsx",  "bus": 21, "kwpeak": 14.44},
    "pv_Haushalt_5_nord": {"file": "PV/ninja_pv_BHS23_nord.xlsx",  "bus": 20, "kwpeak": 14.59},
    "pv_Haushalt_5_süd":  {"file": "PV/ninja_pv_BHS23_süd.xlsx",   "bus": 20, "kwpeak": 14.59},
}

 
def build_verbrauch():
    #Frisches Verbrauchs-DataFrame aus Haushalts-Excel + SLPs bauen.
    df = pd.read_excel(file_load, index_col=[0, 1], skiprows=1)
    df = df.rename(columns=lastprofile)
    df["baecker"] = baecker_slp.values
    df["restaurant"] = restaurant_slp.values
    df["edeka1"] = edeka_slp.values
    df["edeka2"] = edeka_slp.values
    df["edeka3"] = edeka_slp.values
    df["edeka4"] = edeka_slp.values
    df["doner"] = doner_slp.values
    df["Elektroladen"] = Elektroladen_slp.values
    df["Handwerkladen"] = Handwerkladen_slp.values
    return df

 
#Erstellung eines weiteren Columns bei der Blindleistung
def daten_anpassung(df):
    for col in list(df.columns):
        if col.startswith("pv_"):
            df[f"Blindleistung_{col}"] = 0.0
        else:
            df[f"Blindleistung_{col}"] = (
                df[col] * (1/0.95**2 - 1)**0.5
            ) / 1000
        # kW zu MW
        df[col] = df[col] / 1000
    return df


def create_controller_load(n, df, name,i):
    #einen Controller für die Variable p_mw
    ConstControl(n, 
                element='load', 
                variable='p_mw', 
                element_index=[i],
                 data_source=df, 
                 profile_name=[name],)
    #einen Controller für die Q_mvar 
    ConstControl(n,
                 element='load',
                 variable='q_mvar',
                 element_index=[i],
                 data_source=df,
                 profile_name=[f"Blindleistung_{name}"],
                 )

def create_controller_gen(n, df, name, i):
    ConstControl(n,
                 element='sgen',
                 variable='p_mw',
                 element_index=[i],
                 data_source=df,
                 profile_name=[name])
    ConstControl(n,
                 element='sgen',
                 variable='q_mvar',
                 element_index=[i],
                 data_source=df,
                 profile_name=[f"Blindleistung_{name}"])


def create_data_source(n, profiles):
    ds = DFData(profiles)
        #wir loopen über alle Load_buses und gehen jeden durch, falls der Name von einem Bus übereinstimmt mit load_bus_mapping
        #dann wird ein controller erstellt
    for i, load in n.load.iterrows():
        if load['name'] in profiles.columns:
            create_controller_load(n,ds,load['name'],i)
            #create controller erzeugung
    for i, sgen in n.sgen.iterrows():
        if sgen['name'] in profiles.columns:
            create_controller_gen(n, ds, sgen['name'], i)


def create_output_writer(n, timesteps, output_dir):
    ow = OutputWriter(n, timesteps, output_path=output_dir, output_file_type=".xlsx", log_variables=[])
    # these variables are saved to the harddisk after / during the time series loop
    ow.log_variable('res_load', 'p_mw')
    ow.log_variable('res_bus', 'vm_pu')
    ow.log_variable('res_line', 'loading_percent')
    ow.log_variable('res_line', 'i_ka')
    ow.log_variable('res_sgen', 'p_mw')
    ow.log_variable('res_sgen', 'q_mvar')
    ow.log_variable('res_trafo', 'loading_percent')  
    ow.log_variable('res_trafo', 'p_hv_mw') 
    return ow

optimierung_faktoren = {
    # --- Istzustand ---
    "pv_Haushalt_2":      1.0,  
    "pv_edeka1":          1.0,
    "pv_edeka2":          1.0,
    "pv_edeka3":          1.0,
    "pv_edeka4":          1.0,
    "pv_Handwerkladen":   1.0,  
    # --- Geplant ---
    "pv_Haushalt_1":      0.80,
    "pv_Haushalt_3_ost":  0.80,  
    "pv_Haushalt_3_west": 0.80,  
    "pv_Haushalt_4_süd":  0.80,  
    "pv_Haushalt_4_nord": 0.80,  
    "pv_baecker_ost":     0.80,  
    "pv_baecker_west":    0.80,  
    "pv_restaurant_nord": 0.80,  
    "pv_restaurant_süd":  0.80,  
    "pv_doner_ost":       0.80,  
    "pv_doner_west":      0.80,  
    "pv_Elektroladen":    0.80, 
    "pv_Haushalt_6_ost":  0.80,  
    "pv_Haushalt_6_west": 0.80,  
    "pv_Haushalt_5_nord": 0.80,  
    "pv_Haushalt_5_süd":  0.80,  
}

#Szenario Möglichekeiten: "status_quo", "alle_pv_mit_last", "alle_pv_ohne_last", "60_pv_ohne_last", 60_pv_mit_last
Szenario = ["pv_ohne_last_optimiert"]
for SZENARIO in Szenario:
    if SZENARIO == "status_quo":
        pv_mapping = pv_istzustand
        lasten_aktiv = True
        kappung = False
        faktoren = {}
    elif SZENARIO == "alle_pv_mit_last":
        pv_mapping = {**pv_istzustand, **pv_geplant}
        lasten_aktiv = True
        kappung = False
        faktoren = {}
    elif SZENARIO == "alle_pv_ohne_last":
        pv_mapping = {**pv_istzustand, **pv_geplant}
        lasten_aktiv = False
        kappung = False
        faktoren = {}
    elif SZENARIO == "60_pv_ohne_last":
        pv_mapping = {**pv_istzustand, **pv_geplant}
        lasten_aktiv = False
        kappung = True
        faktoren = {}
    elif SZENARIO == "60_pv_mit_last":
        pv_mapping = {**pv_istzustand, **pv_geplant}
        lasten_aktiv = True
        kappung = True
        faktoren = {}
    elif SZENARIO == "pv_ohne_last_optimiert":
        pv_mapping = {**pv_istzustand, **pv_geplant}
        lasten_aktiv = False
        kappung = True
        faktoren = optimierung_faktoren
    
    Verbrauch_Haushalt = build_verbrauch()

    for name, info in pv_mapping.items():
        pv_df = pd.read_excel(info["file"])
        werte = pv_df["Erzeugung"]
        if werte.dtype == object:
            werte = werte.astype(str).str.replace(",", ".", regex=False)
        werte = pd.to_numeric(werte, errors="coerce")

        # Edeka-PV gleichmäßig auf 4 Stränge aufteilen
        if name.startswith("pv_edeka"):
            werte = werte / 4

        size_faktor = faktoren.get(name, 1.0)
        werte = werte * size_faktor
        kwpeak_effektiv = info["kwpeak"] * size_faktor

        # 60%-Kappung: alles über 60% der Peak-Leistung wird abgeschnitten
        if kappung:
            grenze = 0.6 * kwpeak_effektiv
            werte = werte.clip(upper=grenze)

        Verbrauch_Haushalt[name] = werte.values[:8760]

    Verbrauch_Haushalt = daten_anpassung(df=Verbrauch_Haushalt)
    
    n, bus_info_df = build_network(lines)

    #Load für alle Lastprofile erstellen an die entsprechenden Buses
    for key, value in load_bus_mapping.items():
        # p_mw ist nur ein Platzhalter, wird durch den Zeitreihen-Controller überschrieben
        pp.create_load(n, bus=value, p_mw=0.0, q_mvar=0.0, name=key)

    for name, info in pv_mapping.items():
        pp.create_sgen(n, bus=info["bus"], p_mw=0.0, q_mvar=0.0, name=name)

    if not lasten_aktiv:
        n.load['in_service'] = False

    create_data_source(n, Verbrauch_Haushalt)
    # Erstelle ein Load-Element pro Haushalt, das später mit dem Zeitreihenprofil gesteuert wird.
    output_dir = f"results_{SZENARIO}" 
    os.makedirs(output_dir, exist_ok=True) 

    timesteps = range(len(Verbrauch_Haushalt.index))
    pp.runpp(n)
    ow = create_output_writer(n, timesteps, output_dir=output_dir)
    run_timeseries(n, timesteps)

    
    