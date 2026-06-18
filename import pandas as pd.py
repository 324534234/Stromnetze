import pandas as pd
import pandapower as pp
import pandapower.plotting as plot
from pandapower.timeseries import DFData, OutputWriter, run_timeseries
from pandapower.control import ConstControl

file_load = r"C:\Users\Noah\Desktop\EE TH Köln\Semester 2\Stromnetze\Daten\OneDrive_1_14.6.2026\Lastprofile.xlsx"
file_lines = r"C:\Users\Noah\Desktop\EE TH Köln\Semester 2\Stromnetze\Daten\Stromnetze_Auslegungsdaten - Kopie.xlsx"


lines = pd.read_excel(file_lines, index_col=0)
lines = lines.rename(columns={"Länge": "Laenge"})

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

#Umbennen der Columnsudn anschließend einfügen an die Buses
lastprofile = {
    1:"Haushalt_1",
    2:"Haushalt_2",
    3:"Haushalt_3",
    4:"Haushalt_4"
}
# Mapping von Haushaltsnamen auf Busindizes.
load_bus_mapping = {
    "Haushalt_1": 6,
    "Haushalt_2": 7,
    "Haushalt_3": 10,
    "Haushalt_4": 11,
}

Verbrauch_Haushalt = pd.read_excel(file_load, index_col=[0,1], skiprows=1)
#Spaltennamen anpassen
Verbrauch_Haushalt= Verbrauch_Haushalt.rename(columns=lastprofile)
def Daten_Anpassung(df):
    for col in list(df.columns):
        df[f"Blindleistung_{col}"] = (
            df[col] * (1/0.95**2 - 1)**0.5
        )
        # kW zu MW
        df[col] = df[col] / 1000
        df[f"Blindleistung_{col}"] = (
            df[f"Blindleistung_{col}"] / 1000
        )

    return df
Verbrauch_Haushalt = Daten_Anpassung(df=Verbrauch_Haushalt)

print(Verbrauch_Haushalt)

#Load für alle Lastprofile erstellen an die entsprechenden Buses
for key, value in load_bus_mapping.items():
    pp.create_load(n, bus=value, p_mw=0.1, q_mvar=0.0, name=key)

#
def create_data_source(n):
    profiles = Verbrauch_Haushalt
    ds = DFData(profiles)
        #wir loopen über alle Load_buses und gehen jeden durch, falls der Name von einem Bus übereinstimmt mit load_bus_mapping
        #dann wird ein controller erstellt
    for i, load in n.load.iterrows():
        if load['name'] in profiles.columns:
            create_controller_load(n,ds,load['name'],i)
    return  n

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

'''
def create_controller_gen(net,df,x, name, MWp,Scheinleistung):
    pp.create_sgen(net, bus=x,p_mw= MWp, q_mvar= Scheinleistung )
    pp.ConstControl(net, element='sgen', variable='p_mw', element_index=[0],
                 data_source=df[{name}], profile_name=[f"{name}"])

'''


# Erstelle ein Load-Element pro Haushalt, das später mit dem Zeitreihenprofil gesteuert wird.


def create_output_writer(n, timesteps, output_dir):
    ow = OutputWriter(n, timesteps, output_path=output_dir, output_file_type=".xlsx", log_variables=[])
    # these variables are saved to the harddisk after / during the time series loop
    ow.log_variable('res_load', 'p_mw')
    ow.log_variable('res_bus', 'vm_pu')
    ow.log_variable('res_line', 'loading_percent')
    ow.log_variable('res_line', 'i_ka')
    ow.log_variable('res_gen', 'p_mw')
    ow.log_variable('res_gen', 'q_mvar')
    return ow

timesteps = range(len(Verbrauch_Haushalt.index))
n = create_data_source(n)
pp.runpp(n)
ow = create_output_writer(n, timesteps, output_dir="results")
run_timeseries(n,timesteps)

print(n.bus)
#print(n.trafo)
print(n.line)
print(n.load)
print(n.controller)

