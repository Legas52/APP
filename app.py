from flask import Flask, render_template, request
import pyodbc
import pandas as pd
from datetime import datetime, timedelta

app = Flask(__name__)
def get_asistencia():
    semana_actual = datetime.now().isocalendar()[1]
    excel_file = r"C:\Users\Lenovo ThinkPad\PycharmProjects\NuevoQRKC\Input\Asistencia QRQC1.xlsx"
    hoja = f'Semana {semana_actual}'
    df = pd.read_excel(excel_file, sheet_name=hoja,skiprows=2,usecols='B:I',header=None)
    nan_rows = df.isna().all(axis=1)
    nan_indices = nan_rows[nan_rows].index
    nan_indices = nan_indices.tolist() + [len(df)]
    dfs = []
    prev_index = 0
    for index in nan_indices:
        if prev_index != index:
            sub_df = df.iloc[prev_index:index]
            dfs.append(sub_df)
        prev_index = index + 1
    html_tables = [sub_df.to_html(index=False, header=False, na_rep='') for sub_df in dfs]
    aditional_df = pd.read_excel(excel_file, sheet_name=hoja,skiprows=2,usecols='K:L',header=0)
    aditional_df = aditional_df.to_html(index= False,header=True, na_rep='')
    return html_tables,aditional_df

def get_data(start_date=None, end_date=None):
    conn = pyodbc.connect('DRIVER={SQL Server};'
                          'SERVER=DESKTOP-SH8DNKO\\SQLEXPRESS;'
                          'DATABASE=Productividad;'
                          'UID=sa;'
                          'PWD=AdminDMU2024')
    if start_date and end_date:
        query = (
            f"SELECT Fecha, Prensa, Molde, ROUND(T_E_min,2) as [T_std], [Turno_Efect] as Turno, Minutos_Efectivos as [T Disp],"
            "[Prog_SP],[Producido_Real] as Real, ROUND(Efect_Tot * 100,2) as Efec_T, [Paros_No_ProgramadosPNP] as PNP, [Prog_CP],"
            "ROUND(convert(float,[Efect_Prod])*100,2) as Efect_Prod, Nombre, [Numero_de_Parte] as Parte FROM QRKC "
            f"WHERE Fecha BETWEEN '{start_date}' AND '{end_date}' ORDER BY Prensa, dbo.QRKC.Turno"
        )
    else:
        query = (
            "SELECT Fecha, Prensa, Molde, ROUND(T_E_min,2) as [T_std], [Turno_Efect] as Turno, Minutos_Efectivos as [T Disp],"
            "[Prog_SP],[Producido_Real] as Real, ROUND(Efect_Tot * 100,2) as Efec_T, [Paros_No_ProgramadosPNP] as PNP, [Prog_CP],"
            "ROUND(convert(float,[Efect_Prod])*100,2) as Efect_Prod, Nombre, [Numero_de_Parte] as Parte FROM QRKC ORDER BY Prensa, dbo.QRKC.Turno"
        )
    df = pd.read_sql(query, conn)
    query_turnos = "SELECT Turno, Horario FROM Turnos"
    df_turnos = pd.read_sql(query_turnos, conn)
    conn.close()
    df['Fecha'] = pd.to_datetime(df['Fecha'])
    if start_date and end_date:
        mask = (df['Fecha'] >= start_date) & (df['Fecha'] <= end_date)
        df = df.loc[mask]
    df['PNP'] = pd.to_numeric(df['PNP'], errors='coerce')
    df['Efect_Prod'] = df.apply(lambda x: x['Efec_T'] if x['PNP'] == 0 else x['Efect_Prod'], axis=1)
    df['Efect_Prod'] = pd.to_numeric(df['Efect_Prod'], errors='coerce')
    df['Efec_T'] = pd.to_numeric(df['Efec_T'], errors='coerce')
    efficiencies_by_turno = df.groupby(['Fecha', 'Turno']).agg(
        {'Efec_T': 'mean', 'Efect_Prod': 'mean'}
    ).reset_index().round(2)
    daily_averages = df.groupby('Fecha').agg(
        {'Efec_T': 'mean', 'Efect_Prod': 'mean'}
    ).reset_index().round(2)
    efficiencies_by_turno_grouped = efficiencies_by_turno.groupby('Fecha').apply(
        lambda x: x.to_dict(orient='records')
    ).to_dict()
    daily_averages_grouped = daily_averages.set_index('Fecha').T.to_dict()
    turnos_dict = df_turnos.set_index('Turno')['Horario'].to_dict()
    return df, efficiencies_by_turno_grouped, daily_averages_grouped, turnos_dict

@app.route('/asistencia')
def asistencia():
    tablas_html, extra_df = get_asistencia()
    return render_template('asistencia.html', tables=tablas_html,additional_table=extra_df)

@app.route('/', methods=['GET', 'POST'])
def index():
    start_date, end_date = None, None
    if request.method == 'POST' and request.form['week']:
        year, week_num = map(int, request.form['week'].split('-W'))
        start_date = datetime.strptime(f'{year} {week_num} 0', '%Y %W %w') - timedelta(days=6)
        end_date = start_date + timedelta(days=6)
    df, efficiencies_by_turno, daily_averages, turnos_dict = get_data(start_date.strftime('%Y-%m-%d') if start_date else None,
                                                                      end_date.strftime('%Y-%m-%d') if end_date else None)
    overall_average_efec_t = df['Efec_T'].mean()
    overall_average_efect_prod = df['Efect_Prod'].mean()
    overall_average_efec_t = round(overall_average_efec_t,2)
    overall_average_efect_prod = round(overall_average_efect_prod,2)
    df['Turno'] = df['Turno'].astype(int)
    data_by_date = df.groupby(df['Fecha'].dt.date).apply(lambda x: x.to_dict(orient='records')).to_dict()
    dates = sorted(data_by_date.keys())
    subcolumns = df.columns.tolist()
    return render_template('index.html', week=request.form.get('week', ''), dates=dates, subcolumns=subcolumns,
                           data_by_date=data_by_date, efficiencies_by_turno=efficiencies_by_turno,
                           daily_averages=daily_averages, turnos_dict=turnos_dict,
                           overall_average_efec_t=overall_average_efec_t, overall_average_efect_prod=overall_average_efect_prod)

@app.route('/home')
def home():
    return render_template('home.html')

def get_clientes():
    conn = pyodbc.connect(
        'DRIVER={SQL Server};'
        'SERVER=DESKTOP-SH8DNKO\SQLEXPRESS;'
        'DATABASE=Etiquetado;'
        'UID=sa;'
        'PWD=AdminDMU2024'
    )
    query = "SELECT DISTINCT Cliente FROM Packing"  # Cambia 'PackingList' por el nombre de tu tabla
    df = pd.read_sql(query, conn)
    conn.close()
    return df['Cliente'].tolist()
def get_packing_list(cliente=None, fecha=None):
    conn = pyodbc.connect(
        'DRIVER={SQL Server};'
        'SERVER=DESKTOP-SH8DNKO\SQLEXPRESS;'
        'DATABASE=Etiquetado;'
        'UID=sa;'
        'PWD=AdminDMU2024'
    )

    # Consulta básica
    query = """
        SELECT 
            Modelo,
            Pieza AS [Código],
            SNP,
            Requerimiento as Unidades,
            Cajas,
            Cliente,
            Fecha
        FROM Packing
        WHERE 1=1
    """

    # Aplicar filtros si están presentes
    if cliente:
        query += f" AND Cliente = '{cliente}'"
    if fecha:
        query += f" AND Fecha = '{fecha}'"

    query += " ORDER BY Modelo, Pieza"
    df = pd.read_sql(query, conn)
    conn.close()

    return df

@app.route('/packing-list', methods=['GET', 'POST'])
def packing_list():
    clientes = get_clientes()  # Lista de clientes para el dropdown
    selected_cliente = None
    selected_fecha = None
    df = pd.DataFrame()

    if request.method == 'POST':
        selected_cliente = request.form.get('cliente')
        selected_fecha = request.form.get('fecha')
        df = get_packing_list(cliente=selected_cliente, fecha=selected_fecha)
    else:
        df = get_packing_list()

    # Agrupar datos por modelo y generar un diccionario
    packing_data = {}
    for modelo, grupo in df.groupby("Modelo"):
        packing_data[modelo] = grupo.to_dict(orient="records")

    return render_template(
        'packing_list.html',
        packing_data=packing_data,
        clientes=clientes,
        selected_cliente=selected_cliente,
        selected_fecha=selected_fecha
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
