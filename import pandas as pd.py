import pandas as pd
import pandapower as pp
import pandapower.plotting as plot
from pandapower.timeseries import DFData, OutputWriter, run_timeseries
from pandapower.control import ConstControl
from demandlib import bdew #für Standardlastprofile


file_load = "Lastprofile.xlsx"
file_lines = "Stromnetze_Auslegungsdaten - Kopie.xlsx"


lines = pd.read_excel(file_lines, index_col=0)
lines = lines.rename(columns={"Länge": "Laenge"})

#Erstellen der Standardlastprofile
slp = bdew.ElecSlp(2021)

baecker_slp = slp.get_scaled_power_profiles({"g5": 25000}).resample("h").sum()
restaurant_slp = slp.get_scaled_power_profiles({"g2": 45000}).resample("h").sum()
edeka_slp = slp.get_scaled_power_profiles({"g4": 130000}).resample("h").sum()
doner_slp = slp.get_scaled_power_profiles({"g4": 15000}).resample("h").sum()
Elektroladen_slp = slp.get_scaled_power_profiles({"g4": 15000}).resample("h").sum()
Handwerkladen_slp = slp.get_scaled_power_profiles({"g3": 105000}).resample("h").sum()

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
    #df = df.loc[[Kabelnummer]]
    for i in range(len(df)):
        buses[f"Bus_LV{Kabelnummer}.{i}"] = pp.create_bus(n, name=f"busLV{Kabelnummer}.{i}", vn_kv=0.4, type="n")
    return n

def Line_erstellen(df, Kabelnummer: int):
    #df = df.sort_index()
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
                       std_type=typ, #Kabeltyp muss noch definiert werden
                       name=f"Kabel_{Kabelnummer}_{i}")
    return n


pp.create_ext_grid(n, bus=b1, vm_pu=1.02, name="grid_connection")

for l, group in lines.groupby(level=0):
    extraction(group, l)

abzweig_start = {
    91: buses["Bus_LV9.0"],  
}
 
for l, group in lines.groupby(level=0):
    Line_erstellen(group, l)

bus_info = []
for l, group in lines.groupby(level=0):
    for i, row in enumerate(group.itertuples()):
        bus_name = f"busLV{l}.{i}"
        bus_idx = n.bus[n.bus['name'] == bus_name].index[0]
        bus_info.append({"index": bus_idx, "name": bus_name, "endpunkt": row.Endpunkt})
print(pd.DataFrame(bus_info))


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
    "Haushalt_1": 3,
    "Haushalt_2": 7,
    "Haushalt_3": 23,
    "Haushalt_4": 18,
    "Haushalt_5": 19,
    "Haushalt_6": 20,
    "baecker": 22,
    "restaurant": 9,
    "edeka1": 15,
    "edeka2":16,
    "edeka3": 14, 
    "edeka4": 12, 
    "doner": 5,
    "Elektroladen": 6,
    "Handwerkladen": 8  
}

pv_mapping = {
    "pv_Haushalt_1": {"file": "PV/ninja_pv_BHS35.xlsx", "bus": 3},
    "pv_Haushalt_2": {"file": "PV/ninja_pv_istzustand_BHS36.xlsx", "bus": 7},
    "pv_Haushalt_3_ost": {"file": "PV/ninja_pv_BHS27a_Ost.xlsx", "bus": 23},
    "pv_Haushalt_3_west": {"file": "PV/ninja_pv_BHS27a_West.xlsx", "bus": 23},
    "pv_Haushalt_4_süd": {"file": "PV/ninja_pv_BHS25_süd.xlsx", "bus": 18},
    "pv_Haushalt_4_nord": {"file": "PV/ninja_pv_BHS25_nord.xlsx", "bus": 18},
    "pv_baecker_ost": {"file": "PV/ninja_pv_BHS27_Ost.xlsx", "bus": 22},
    "pv_baecker_west": {"file": "PV/ninja_pv_BHS27_West.xlsx", "bus": 22},
    "pv_restaurant_nord": {"file": "PV/ninja_pv_BHS38_Nord.xlsx", "bus": 9},
    "pv_restaurant_süd": {"file": "PV/ninja_pv_BHS38_Süd.xlsx", "bus": 9},
    "pv_edeka1": {"file": "PV/ninja_pv_istzustand_BHS29-33.xlsx", "bus": 15},
    "pv_doner_ost": {"file": "PV/ninja_pv_BHS32_Ost.xlsx", "bus": 5},
    "pv_doner_west": {"file": "PV/ninja_pv_BHS32_West.xlsx", "bus": 5},
    "pv_Elektroladen": {"file": "PV/ninja_pv_BHS34.xlsx", "bus": 6},
    "pv_Handwerkladen": {"file": "PV/ninja_pv_istzustand_BHS36a.xlsx", "bus": 8}
}

print(n.bus)
#print(n.trafo)
print(n.line)
print(n.load)
print(n.controller)

Verbrauch_Haushalt = pd.read_excel(file_load, index_col=[0,1], skiprows=1)

#Spaltennamen anpassen
Verbrauch_Haushalt= Verbrauch_Haushalt.rename(columns=lastprofile)

Verbrauch_Haushalt["baecker"] = baecker_slp.values
Verbrauch_Haushalt["restaurant"] = restaurant_slp.values
Verbrauch_Haushalt["edeka1"] = edeka_slp.values
Verbrauch_Haushalt["edeka2"] = edeka_slp.values
Verbrauch_Haushalt["edeka3"] = edeka_slp.values
Verbrauch_Haushalt["edeka4"] = edeka_slp.values
Verbrauch_Haushalt["doner"] = doner_slp.values
Verbrauch_Haushalt["Elektroladen"] = Elektroladen_slp.values
Verbrauch_Haushalt["Handwerkladen"] = Handwerkladen_slp.values

for name, info in pv_mapping.items():
    pv_df = pd.read_excel(info["file"])
    werte = pv_df["Erzeugung"]
    if werte.dtype == object:
        werte = werte.astype(str).str.replace(",", ".", regex=False)
    werte = pd.to_numeric(werte, errors="coerce")
    Verbrauch_Haushalt[name] = werte.values[:8760]

def Daten_Anpassung(df):
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


Verbrauch_Haushalt = Daten_Anpassung(df=Verbrauch_Haushalt)

print(Verbrauch_Haushalt)

#Load für alle Lastprofile erstellen an die entsprechenden Buses
for key, value in load_bus_mapping.items():
    pp.create_load(n, bus=value, p_mw=0.1, q_mvar=0.0, name=key)

for name, info in pv_mapping.items():
    pp.create_sgen(n, bus=info["bus"], p_mw=0.0, q_mvar=0.0, name=name)


#Blindleistung berechnen


#q[i] = p[i] * (1/cosphi[i]**2 -1)**0.5


def create_controller_load(n, df, name,i):
    #einen Controller für die Variable p_mw
    ConstControl(n, 
                element='load', 
                variable='p_mw', 
                element_index=[i],
                 data_source=df, 
                 profile_name=[name],)
    #einen Controller für die Q_mvar - muss noch weiter angepasst werden
    ConstControl(n,
                 element='load',
                 variable='q_mvar',
                 element_index=[i],
                 data_source=df,
                 profile_name=[f"Blindleistung_{name}"],
                 )
    return n

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
    return n


def create_data_source(n):
    profiles = Verbrauch_Haushalt
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

    return  n

'''
def create_controller_gen(net,df,x, name, MWp,Scheinleistung):
    pp.create_sgen(net, bus=x,p_mw= MWp, q_mvar= Scheinleistung )
    pp.ConstControl(net, element='sgen', variable='p_mw', element_index=[0],
                 data_source=df[{name}], profile_name=[f"{name}"])

'''


# Erstelle ein Load-Element pro Haushalt, das später mit dem Zeitreihenprofil gesteuert wird.
output_dir = "results"

def create_output_writer(n, timesteps, output_dir):
    ow = OutputWriter(n, timesteps, output_path=output_dir, output_file_type=".xlsx", log_variables=[])
    # these variables are saved to the harddisk after / during the time series loop
    ow.log_variable('res_load', 'p_mw')
    ow.log_variable('res_bus', 'vm_pu')
    ow.log_variable('res_line', 'loading_percent')
    ow.log_variable('res_line', 'i_ka')
    ow.log_variable('res_sgen', 'p_mw')
    ow.log_variable('res_sgen', 'q_mvar')
    return ow

timesteps = range(len(Verbrauch_Haushalt.index))
n = create_data_source(n)
#n.load['in_service'] = False # Ohne Lasten simulieren
pp.runpp(n)
ow = create_output_writer(n, timesteps, output_dir="results")
run_timeseries(n, timesteps)

import matplotlib.pyplot as plt
import os

x_label = "time step"
# voltage results
vm_pu_file = os.path.join(output_dir, "res_bus", "vm_pu.xlsx")
vm_pu = pd.read_excel(vm_pu_file, index_col=0)
vm_pu.plot(label="vm_pu")
plt.xlabel(x_label)
plt.ylabel("voltage mag. [p.u.]")
plt.title("Voltage Magnitude")
plt.grid()
plt.show()

# line loading results
ll_file = os.path.join(output_dir, "res_line", "loading_percent.xlsx")
line_loading = pd.read_excel(ll_file, index_col=0)
line_loading.plot(label="line_loading")
plt.xlabel(x_label)
plt.ylabel("line loading [%]")
plt.title("Line Loading")
plt.grid()
plt.show()

# load results
load_file = os.path.join(output_dir, "res_load", "p_mw.xlsx")
load = pd.read_excel(load_file, index_col=0)
load.plot(label="load")
plt.xlabel(x_label)
plt.ylabel("P [MW]")
plt.grid()
plt.show()

# generation results [p_mw]
gen_file = os.path.join(output_dir, "res_sgen", "p_mw.xlsx")
gen = pd.read_excel(gen_file, index_col=0)
gen.plot(label="gen")
plt.xlabel(x_label)
plt.ylabel("P [MW]")
plt.grid()
plt.show()

# generation results [q_mvar]
gen_file = os.path.join(output_dir, "res_sgen", "q_mvar.xlsx")
gen = pd.read_excel(gen_file, index_col=0)
gen.plot(label="gen")
plt.xlabel(x_label)
plt.ylabel("Q [Mvar]")
plt.grid()
plt.show()





