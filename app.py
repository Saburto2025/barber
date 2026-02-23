import streamlit as st
import sqlite3
import datetime
import hashlib
import os

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Software Merka 4.0",
    page_icon="✂️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- FOOTER ---
def mostrar_footer():
    st.markdown("""
        <style>
        .footer {
            position: fixed;
            left: 0;
            bottom: 0;
            width: 100%;
            background-color: #0e1117;
            color: white;
            text-align: center;
            padding: 10px;
            font-size: 0.9rem;
            border-top: 1px solid #333;
            z-index: 999;
        }
        </style>
        <div class="footer">
            Software Merka 4.0 &nbsp;|&nbsp; 📞 +506 6449 8045
        </div>
    """, unsafe_allow_html=True)

# --- BASE DE DATOS (CORREGIDA PARA NUBE) ---
def get_db_connection():
    # AGREGADO: check_same_thread=False permite que Streamlit funcione sin bloqueos
    conn = sqlite3.connect('barberia.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row 
    return conn

def init_db():
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Tabla Servicios
        c.execute('''CREATE TABLE IF NOT EXISTS servicios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            precio REAL,
            comision REAL
        )''')
        
        # Tabla Barberos
        c.execute('''CREATE TABLE IF NOT EXISTS barberos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            rol TEXT
        )''')

        # Tabla Tickets
        c.execute('''CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT,
            whatsapp TEXT,
            barbero_id INTEGER,
            total REAL,
            propina REAL,
            fecha TEXT,
            metodo_pago TEXT,
            FOREIGN KEY(barbero_id) REFERENCES barberos(id)
        )''')

        # Tabla Detalles
        c.execute('''CREATE TABLE IF NOT EXISTS detalles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER,
            servicio TEXT,
            precio REAL
        )''')

        # Migración segura para agregar WhatsApp si no existe
        c.execute("PRAGMA table_info(tickets)")
        columns = [info[1] for info in c.fetchall()]
        if 'whatsapp' not in columns:
            c.execute("ALTER TABLE tickets ADD COLUMN whatsapp TEXT")

        # Datos Iniciales (Solo si está vacío)
        c.execute("SELECT count(*) FROM servicios")
        if c.fetchone()[0] == 0:
            servicios_def = [
                ("Corte Clásico", 150, 50),
                ("Barba Express", 100, 50),
                ("Premium (Corte+Barba)", 300, 60),
                ("Producto: Pomada", 200, 20)
            ]
            c.executemany("INSERT INTO servicios (nombre, precio, comision) VALUES (?, ?, ?)", servicios_def)

        c.execute("SELECT count(*) FROM barberos")
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO barberos (nombre, rol) VALUES ('Juan', 'Barbero')")
            c.execute("INSERT INTO barberos (nombre, rol) VALUES ('Dueño', 'Admin')")
        
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Error al iniciar base de datos: {e}")

# --- SISTEMA DE LOGIN ---
def login():
    st.title("🔐 Acceso al Sistema")
    
    st.markdown("""
        <style>
        .googlesignin {
            background-color: #4285F4;
            color: white;
            padding: 12px;
            border-radius: 4px;
            text-align: center;
            font-weight: bold;
            cursor: pointer;
            margin-bottom: 20px;
            display: block;
            text-decoration: none;
        }
        </style>
        <a href="#" class="googlesignin">G Iniciar sesión con Google</a>
    """, unsafe_allow_html=True)
    
    st.markdown("--- O ingresa con tu cuenta interna ---")
    
    username = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")
    
    if st.button("Entrar"):
        if username == "admin" and password == "1234":
            st.session_state['logged_in'] = True
            st.session_state['role'] = 'Admin'
            st.rerun()
        elif username == "barbero" and password == "1234":
            st.session_state['logged_in'] = True
            st.session_state['role'] = 'Barbero'
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos")

# --- PANTALLA PRINCIPAL ---
def main_app():
    init_db()

    with st.sidebar:
        st.title("Menú Principal")
        st.write(f"Hola, **{st.session_state['role']}**")
        
        if st.button("📝 Nueva Venta"):
            st.session_state.view = 'Venta'
        if st.button("📊 Monitor Dueño"):
            st.session_state.view = 'Monitor'
        
        if st.button("🚪 Cerrar Sesión"):
            st.session_state['logged_in'] = False
            st.rerun()

    if 'view' not in st.session_state:
        st.session_state.view = 'Venta'

    if st.session_state.view == 'Venta':
        pantalla_venta()
    elif st.session_state.view == 'Monitor':
        if st.session_state['role'] == 'Admin':
            pantalla_monitor()
        else:
            st.warning("Acceso restringido solo para Administradores.")

    mostrar_footer()

# --- VISTA 1: NUEVA VENTA ---
def pantalla_venta():
    st.header("✂️ Nueva Venta / Ticket")
    
    try:
        conn = get_db_connection()
        barberos = conn.execute("SELECT * FROM barberos WHERE rol != 'Admin'").fetchall()
        servicios = conn.execute("SELECT * FROM servicios").fetchall()
        
        # Validación por si no hay datos
        if not barberos: st.warning("No hay barberos registrados.")
        if not servicios: st.warning("No hay servicios configurados.")

        with st.form("form_venta"):
            col1, col2 = st.columns(2)
            with col1:
                cliente = st.text_input("Nombre del Cliente")
            with col2:
                whatsapp = st.text_input("WhatsApp (Cliente)", placeholder="+506 ...")
            
            # Asegurar que hay barberos antes de mostrar el selectbox
            nombres_barberos = [b['nombre'] for b in barberos] if barberos else ["Sin barberos"]
            barbero_sel = st.selectbox("Barbero", nombres_barberos, disabled=not barberos)
            
            st.subheader("Seleccionar Servicios")
            nombres_servicios = [s['nombre'] for s in servicios] if servicios else []
            
            # Función auxiliar para formato
            def format_servicio(nombre):
                s = next((x for x in servicios if x['nombre'] == nombre), None)
                return f"{nombre} (${s['precio']})" if s else nombre

            servicios_sel = st.multiselect(
                "Servicios/Productos", 
                nombres_servicios,
                format_func=format_servicio,
                disabled=not servicios
            )
            
            col3, col4 = st.columns(2)
            with col3:
                propina = st.number_input("Propina", min_value=0.0, step=10.0)
            with col4:
                metodo_pago = st.selectbox("Método de Pago", ["Efectivo", "Tarjeta", "Sinpe Móvil"])
            
            submit = st.form_submit_button("💾 Guardar y Cobrar", use_container_width=True, type="primary")

            if submit:
                if not cliente or not servicios_sel:
                    st.error("Falta nombre del cliente o servicios.")
                else:
                    total_servicios = 0
                    barbero_id = next((b['id'] for b in barberos if b['nombre'] == barbero_sel), None)
                    
                    if not barbero_id:
                        st.error("Error al identificar barbero.")
                    else:
                        fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO tickets (cliente, whatsapp, barbero_id, total, propina, fecha, metodo_pago)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (cliente, whatsapp, barbero_id, 0, propina, fecha, metodo_pago))
                        
                        ticket_id = cursor.lastrowid
                        
                        for serv_nombre in servicios_sel:
                            serv_data = next(s for s in servicios if s['nombre'] == serv_nombre)
                            precio = serv_data['precio']
                            total_servicios += precio
                            
                            cursor.execute("""
                                INSERT INTO detalles (ticket_id, servicio, precio)
                                VALUES (?, ?, ?)
                            """, (ticket_id, serv_nombre, precio))
                        
                        total_final = total_servicios + propina
                        cursor.execute("UPDATE tickets SET total = ? WHERE id = ?", (total_final, ticket_id))
                        
                        conn.commit()
                        conn.close()
                        
                        st.success(f"✅ Venta Exitosa! Total: ${total_final}")
                        st.balloons()
                        st.rerun()
    except Exception as e:
        st.error(f"Ocurrió un error: {e}")

# --- VISTA 2: MONITOR ---
def pantalla_monitor():
    st.header("📊 Monitor en Tiempo Real - Sucursal Centro")
    
    try:
        conn = get_db_connection()
        hoy = datetime.date.today()
        fecha_filtro = st.date_input("Ver fecha:", hoy)
        
        query = """
            SELECT t.id, t.cliente, t.whatsapp, b.nombre as barbero, t.total, t.propina, t.fecha, t.metodo_pago
            FROM tickets t
            JOIN barberos b ON t.barbero_id = b.id
            WHERE DATE(t.fecha) = ?
            ORDER BY t.fecha DESC
        """
        
        resultados = conn.execute(query, (str(fecha_filtro),)).fetchall()
        conn.close()
        
        if not resultados:
            st.info("No hay ventas registradas para esta fecha.")
            return

        total_caja = sum(r['total'] for r in resultados)
        total_propinas = sum(r['propina'] for r in resultados)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Ventas Totales", f"${total_caja:,.2f}")
        col2.metric("Propinas Entregadas", f"${total_propinas:,.2f}")
        col3.metric("Tickets Atendidos", len(resultados))
        
        st.divider()
        
        st.subheader("Detalle de Transacciones")
        for r in resultados:
            with st.expander(f"🧾 Ticket #{r['id']} - {r['cliente']} (Barbero: {r['barbero']})"):
                c1, c2, c3 = st.columns(3)
                c1.write(f"**Hora:** {r['fecha'].split(' ')[1]}")
                c2.write(f"**Pago:** {r['metodo_pago']}")
                c3.write(f"**WhatsApp:** {r['whatsapp'] if r['whatsapp'] else 'N/A'}")
                
                # Cargar detalles de forma segura
                try:
                    conn_det = get_db_connection()
                    detalles = conn_det.execute("SELECT servicio, precio FROM detalles WHERE ticket_id = ?", (r['id'],)).fetchall()
                    conn_det.close()
                    
                    st.write("**Servicios:**")
                    for d in detalles:
                        st.write(f"- {d['servicio']}: ${d['precio']}")
                except:
                    st.write("Error cargando detalles.")

                st.write(f"💰 **Total Ticket:** ${r['total']}")

        if st.button("🔄 Actualizar Datos"):
            st.rerun()
    except Exception as e:
        st.error(f"Error al cargar reporte: {e}")

# --- EJECUCIÓN ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if st.session_state['logged_in']:
    main_app()
else:
    login()
