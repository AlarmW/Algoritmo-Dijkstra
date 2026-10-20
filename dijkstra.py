import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import networkx as nx
import matplotlib.pyplot as plt
import random, time, math, re
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# =========================================================
#  GEOMETRÍA: coordenadas y pesos euclidianos
# =========================================================
COORD_MIN, COORD_MAX = 0, 100
EPS = 1e-9   # tolerancia para comparar distancias decimales
DIST_MIN_NODOS = 16   # separación mínima entre nodos al generarlos (deja espacio para ver los pesos)
RADIO_NODO = 4        # radio aproximado de un nodo en unidades de datos (para ubicar etiquetas)
NODE_SIZE = 450       # tamaño de los nodos en el dibujo (menor = más espacio para las etiquetas)

def distancia_euclidiana(p, q):
    """d(u,v) = sqrt((xv-xu)^2 + (yv-yu)^2)"""
    return math.hypot(q[0] - p[0], q[1] - p[1])

def generar_posiciones(n, dist_min=DIST_MIN_NODOS):
    """Genera n posiciones enteras (x, y) en [0,100], distintas y separadas
    al menos dist_min. Si no es posible, relaja dist_min gradualmente."""
    while True:
        posiciones = []
        ok = True
        for _ in range(n):
            for _ in range(2000):
                p = (random.randint(COORD_MIN, COORD_MAX), random.randint(COORD_MIN, COORD_MAX))
                if all(distancia_euclidiana(p, q) >= dist_min for q in posiciones):
                    posiciones.append(p)
                    break
            else:
                ok = False
                break
        if ok:
            return posiciones
        dist_min *= 0.9   # relaja la separación y reintenta

def agregar_arista_geo(G, u, v):
    """Agrega u->v con peso = distancia euclidiana (precisión completa)."""
    G.add_edge(u, v, weight=distancia_euclidiana(G.nodes[u]['pos'], G.nodes[v]['pos']))

def fmt_peso(w):
    """Formato de visualización: entero más cercano (el valor interno no se redondea)."""
    return str(int(math.floor(w + 0.5)))

def fmt_dist(dist):
    return "{" + ", ".join(f"{k}: {'inf' if d == float('inf') else fmt_peso(d)}" for k, d in dist.items()) + "}"

# =========================================================
#  GENERACIÓN POR PROXIMIDAD (modo aleatorio)
# =========================================================
# Límite máximo de distancia euclidiana permitido para una arista generada
# automáticamente (en las mismas unidades que las coordenadas 0-100).
# Valor predeterminado: 40.0. Súbalo para grafos más densos/fáciles de conectar;
# bájelo para conexiones más locales (puede volverse imposible conectar el grafo).
DIST_MAX_ARISTA = 40.0
K_VECINOS_MAX = 3        # cada nodo se conecta a 1..K de sus vecinos más próximos (dentro del límite)
PROB_EXTRA = 0.10        # probabilidad de una arista extra entre pares que ya están dentro del límite
MAX_INTENTOS = 300       # reintentos con nuevas posiciones antes de rendirse

class GrafoNoGenerable(Exception):
    """No se pudo generar un grafo fuertemente conexo respetando el límite de distancia."""

def pares_dentro_del_limite(G, dist_max):
    """Lista ordenada (distancia, u, v) de todos los pares dirigidos con d <= dist_max."""
    pares = []
    for u in G.nodes:
        for v in G.nodes:
            if u != v:
                d = distancia_euclidiana(G.nodes[u]['pos'], G.nodes[v]['pos'])
                if d <= dist_max:
                    pares.append((d, u, v))
    pares.sort()
    return pares

def conectar_vecinos_cercanos(G, dist_max):
    """Cada nodo apunta a 1..K_VECINOS_MAX de sus vecinos más cercanos dentro del límite;
    después se agregan algunas aristas extra aleatorias, también dentro del límite."""
    pares = pares_dentro_del_limite(G, dist_max)
    for u in G.nodes:
        cercanos = [v for d, a, v in pares if a == u]          # ya ordenados por distancia
        if cercanos:
            for v in cercanos[:random.randint(1, min(K_VECINOS_MAX, len(cercanos)))]:
                agregar_arista_geo(G, u, v)
    for d, u, v in pares:
        if not G.has_edge(u, v) and random.random() < PROB_EXTRA:
            agregar_arista_geo(G, u, v)

def recuperar_conectividad(G, dist_max):
    """Intenta que el grafo dirigido sea fuertemente conexo SIN superar dist_max.
    Cada paso agrega la arista más corta (dentro del límite) que cierra un ciclo entre
    componentes fuertes distintas; si el grafo ni siquiera es débilmente conexo, primero
    une componentes con la arista válida más corta. Devuelve False si no es posible."""
    pares = pares_dentro_del_limite(G, dist_max)
    while not nx.is_strongly_connected(G):
        comp = {x: i for i, c in enumerate(nx.strongly_connected_components(G)) for x in c}
        alcanza = {u: nx.descendants(G, u) for u in G.nodes}
        elegido = None
        for d, u, v in pares:                       # u->v cierra un ciclo si v ya alcanza a u
            if not G.has_edge(u, v) and comp[u] != comp[v] and u in alcanza[v]:
                elegido = (u, v)
                break
        if elegido is None:                         # grafo desconectado: puente válido más corto
            deb = {x: i for i, c in enumerate(nx.weakly_connected_components(G)) for x in c}
            for d, u, v in pares:
                if deb[u] != deb[v]:
                    elegido = (u, v)
                    break
        if elegido is None:
            return False
        agregar_arista_geo(G, *elegido)
    return True

def verificar_grafo(G, dist_max):
    """True si todas las aristas respetan el límite y su peso es la distancia euclidiana."""
    for u, v, w in G.edges(data='weight'):
        d = distancia_euclidiana(G.nodes[u]['pos'], G.nodes[v]['pos'])
        if d > dist_max or w != d:
            return False
    return True

def generar_grafo_proximidad(n, dist_max=DIST_MAX_ARISTA):
    """Grafo dirigido aleatorio basado en proximidad. Si con unas posiciones no se puede
    conectar respetando el límite, se sortean posiciones nuevas (nunca se agregan aristas largas)."""
    for _ in range(MAX_INTENTOS):
        G = nx.DiGraph()
        for i, p in enumerate(generar_posiciones(n)):
            G.add_node(i, pos=p)
        conectar_vecinos_cercanos(G, dist_max)
        if recuperar_conectividad(G, dist_max) and verificar_grafo(G, dist_max):
            return G
    raise GrafoNoGenerable(
        f"No se pudo generar un grafo de {n} nodos fuertemente conexo con distancia máxima "
        f"por arista = {dist_max:g} tras {MAX_INTENTOS} intentos. "
        f"Aumente DIST_MAX_ARISTA o reduzca el número de nodos.")

# =========================================================
#  FUNCIÓN: Generar grafo (manual o aleatorio)
# =========================================================
def parsear_aristas_manual(texto, G):
    """Lee aristas 'origen destino' separadas por salto de línea, ';' o ','.
    Agrega a G las válidas (peso = distancia euclidiana). Se detiene en 'fin'.
    Devuelve (aristas_nuevas, lineas_invalidas)."""
    nuevas, invalidas = 0, []
    for linea in re.split(r"[\n;,]", texto or ""):
        linea = linea.strip()
        if not linea:
            continue
        if linea.lower() == "fin":
            break
        try:
            partes = linea.split()
            if len(partes) != 2:
                raise ValueError
            u, v = map(int, partes)
            if u not in G.nodes or v not in G.nodes or u == v:
                raise ValueError
        except ValueError:
            invalidas.append(linea)
            continue
        if not G.has_edge(u, v):
            agregar_arista_geo(G, u, v)
            nuevas += 1
    return nuevas, invalidas

def generar_grafo(n, modo, dist_max=DIST_MAX_ARISTA):
    """Modo aleatorio: nodos + aristas por proximidad (puede lanzar GrafoNoGenerable).
    Modo manual: solo crea los nodos con sus coordenadas; las aristas las ingresa el usuario
    después de ver el grafo (ver DijkstraApp.ingresar_aristas_manual / parsear_aristas_manual)."""
    if modo != "manual":
        return generar_grafo_proximidad(n, dist_max)
    G = nx.DiGraph()
    for i, p in enumerate(generar_posiciones(n)):
        G.add_node(i, pos=p)
    return G

# =========================================================
#  FUNCIÓN: Dijkstra paso a paso
# =========================================================
def dijkstra_detallado(G, origen, destino, log_callback=None):
    if log_callback is None:
        log_callback = lambda *_: None
    dist = {n: float('inf') for n in G.nodes}
    pred = {n: [] for n in G.nodes}
    dist[origen] = 0
    visitados = set()

    log_callback("\n PROCESO PASO A PASO DEL ALGORITMO DE DIJKSTRA:")
    log_callback("--------------------------------------------------")

    while len(visitados) < len(G.nodes):
        nodo_actual = None
        min_dist = float('inf')
        for n in G.nodes:
            if n not in visitados and dist[n] < min_dist:
                min_dist = dist[n]
                nodo_actual = n
        if nodo_actual is None:
            break
        visitados.add(nodo_actual)
        log_callback(f"\n  Visitando nodo {nodo_actual} (distancia actual = {fmt_peso(min_dist)})")

        for v in G.neighbors(nodo_actual):
            if v not in visitados:
                nueva = dist[nodo_actual] + G[nodo_actual][v]['weight']
                if nueva < dist[v] - EPS:
                    dist[v] = nueva
                    pred[v] = [nodo_actual]
                    log_callback(f"    Actualiza: {v} = {fmt_peso(nueva)} (vía {nodo_actual})")
                elif abs(nueva - dist[v]) <= EPS:
                    pred[v].append(nodo_actual)
                    log_callback(f"    Alternativo: {v} = {fmt_peso(nueva)} (también vía {nodo_actual})")
        log_callback(f"   Distancias: {fmt_dist(dist)}")
        log_callback(f"   Visitados: {sorted(visitados)}")

    if dist[destino] == float('inf'):
        return [], float('inf')

    caminos = []
    def construir(nodo, actual):
        if nodo == origen:
            caminos.append([origen] + actual[::-1])
            return
        for p in pred[nodo]:
            construir(p, actual + [nodo])
    construir(destino, [])
    return caminos, dist[destino]

# =========================================================
#  FUNCIÓN: Dibujar grafo y camino resaltado
# =========================================================
def dibujar_grafo(G, camino=None):
    fig, ax = plt.subplots(figsize=(7,5))
    pos = {n: G.nodes[n]['pos'] for n in G.nodes}   # coordenadas reales (las usadas para los pesos)
    colores = []
    for n in G.nodes:
        if camino and n in camino:
            if n == camino[0]:
                colores.append('lightgreen')  # origen
            elif n == camino[-1]:
                colores.append('lightcoral')  # destino
            else:
                colores.append('gold')        # intermedios
        else:
            colores.append('skyblue')
    nx.draw_networkx_nodes(G, pos, node_color=colores, node_size=NODE_SIZE, edgecolors='black', ax=ax)
    nx.draw_networkx_labels(G, pos, font_size=10, font_weight='bold', ax=ax)

    # Dibujar aristas normales (gris)
    nx.draw_networkx_edges(G, pos, edge_color='gray', arrows=True, arrowsize=18, width=1.5, alpha=0.6, node_size=NODE_SIZE, ax=ax)
    # Si hay camino, resáltalo en rojo grueso
    if camino and len(camino) > 1:
        aristas = [(camino[i], camino[i+1]) for i in range(len(camino)-1)]
        nx.draw_networkx_edges(G, pos, edgelist=aristas, edge_color='red', arrows=True, arrowsize=25, width=3, node_size=NODE_SIZE, ax=ax)
    # Una sola etiqueta por par: si existen u->v y v->u (mismo peso), se rotula una vez.
    # La etiqueta se coloca a lo largo de la arista en el punto más alejado de los nodos
    # (preferentemente el centro) para que ningún nodo la tape.
    for u, v, w in G.edges(data='weight'):
        if G.has_edge(v, u) and u > v:
            continue
        (x1, y1), (x2, y2) = pos[u], pos[v]
        mejor, mejor_score = (0.5, 0.5), -1
        for t in (0.5, 0.4, 0.6, 0.3, 0.7):
            px, py = x1 + t * (x2 - x1), y1 + t * (y2 - y1)
            libre = min(math.hypot(px - qx, py - qy) for qx, qy in pos.values())
            score = min(libre, RADIO_NODO + 4)          # basta con quedar claramente fuera de los nodos
            if score > mejor_score + 1e-9:
                mejor, mejor_score = (px, py), score
        ang = math.degrees(math.atan2(y2 - y1, x2 - x1))
        if ang > 90: ang -= 180
        if ang < -90: ang += 180
        ax.text(mejor[0], mejor[1], fmt_peso(w), fontsize=8, rotation=ang, rotation_mode='anchor',
                ha='center', va='center', zorder=5,
                bbox=dict(boxstyle='round,pad=0.1', fc='white', ec='none', alpha=0.8))

    ax.set_title("Grafo dirigido (camino mínimo resaltado en rojo)" if camino else "Grafo generado", fontsize=12, fontweight='bold')
    ax.set_xlim(COORD_MIN - 6, COORD_MAX + 6)
    ax.set_ylim(COORD_MIN - 6, COORD_MAX + 6)
    ax.set_xticks(range(0, 101, 20))
    ax.set_yticks(range(0, 101, 20))
    ax.tick_params(left=True, bottom=True, labelleft=True, labelbottom=True)
    ax.set_xlabel("X (0–100)")
    ax.set_ylabel("Y (0–100)")
    ax.set_aspect('equal', adjustable='box')
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    return fig

# =========================================================
#  DIÁLOGO: ingreso manual de aristas (campo multilínea)
# =========================================================
class DialogoAristas(tk.Toplevel):
    """Ventana modal con un cuadro de texto multilínea (simpledialog.askstring solo admite una línea).
    Tras cerrarse, self.resultado contiene el texto ingresado o None si se canceló."""
    def __init__(self, parent, coordenadas, n, texto_inicial=""):
        super().__init__(parent)
        self.title("Ingreso manual de aristas")
        self.resultado = None
        self.transient(parent)
        ttk.Label(self, justify=tk.LEFT, text=(
            f"Ingrese las aristas dirigidas (nodos 0–{n-1}), una por línea o separadas por ';' o ','.\n"
            "Formato: origen destino   (el peso se calcula con las coordenadas)\n"
            "Ejemplo:  0 1  /  1 2   o bien   0 1; 1 2\n"
            "Escriba 'fin' para terminar.\n"
            "Al aceptar, estas aristas reemplazan a las actuales.")).pack(anchor=tk.W, padx=10, pady=(10, 4))
        ttk.Label(self, text="Coordenadas de los nodos (x, y):").pack(anchor=tk.W, padx=10)
        info = scrolledtext.ScrolledText(self, height=6, width=44)
        info.insert("1.0", coordenadas)
        info.configure(state=tk.DISABLED)
        info.pack(padx=10, pady=(0, 6))
        ttk.Label(self, text="Aristas:").pack(anchor=tk.W, padx=10)
        self.texto = tk.Text(self, height=10, width=44)
        self.texto.insert("1.0", texto_inicial)   # al editar, aparecen las aristas actuales
        self.texto.pack(padx=10, pady=(0, 6))
        self.texto.focus_set()
        botones = ttk.Frame(self)
        botones.pack(pady=(0, 10))
        ttk.Button(botones, text="Aceptar", command=self._aceptar).pack(side=tk.LEFT, padx=6)
        ttk.Button(botones, text="Cancelar", command=self.destroy).pack(side=tk.LEFT, padx=6)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.grab_set()
        self.wait_window(self)

    def _aceptar(self):
        self.resultado = self.texto.get("1.0", tk.END)
        self.destroy()

# =========================================================
#  CLASE PRINCIPAL (INTERFAZ)
# =========================================================
class DijkstraApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Algoritmo de Dijkstra - Visualizador")
        self.geometry("1150x720")
        self.config(bg="#f4f6f8")

        self.G = None
        self.modo_grafo = None   # modo con el que se generó el grafo actual
        self.camino_actual = None
        self.distancia_actual = None

        self._crear_ui()

    def _crear_ui(self):
        left = ttk.Frame(self, padding=12)
        left.pack(side=tk.LEFT, fill=tk.Y)

        ttk.Label(left, text=" Controles", font=("Segoe UI", 13, "bold")).pack(pady=8)
        ttk.Label(left, text="Nodos (8–16):").pack(anchor=tk.W)
        self.spin_n = tk.Spinbox(left, from_=8, to=16, width=5)
        self.spin_n.pack(anchor=tk.W)

        ttk.Label(left, text="Modo:").pack(anchor=tk.W, pady=(8,0))
        self.modo_var = tk.StringVar(value="aleatorio")
        ttk.Radiobutton(left, text="Aleatorio", variable=self.modo_var, value="aleatorio").pack(anchor=tk.W)
        ttk.Radiobutton(left, text="Manual", variable=self.modo_var, value="manual").pack(anchor=tk.W)

        ttk.Button(left, text=" Generar grafo", command=self.generar_grafo_ui).pack(fill=tk.X, pady=6)
        ttk.Button(left, text=" Mostrar grafo", command=self.mostrar_grafo_ui).pack(fill=tk.X, pady=4)
        ttk.Button(left, text=" Editar aristas", command=self.editar_aristas_ui).pack(fill=tk.X, pady=4)

        ttk.Label(left, text="Origen:").pack(anchor=tk.W, pady=(10,0))
        self.combo_origen = ttk.Combobox(left, state="readonly")
        self.combo_origen.pack(anchor=tk.W, fill=tk.X)
        ttk.Label(left, text="Destino:").pack(anchor=tk.W, pady=(6,0))
        self.combo_destino = ttk.Combobox(left, state="readonly")
        self.combo_destino.pack(anchor=tk.W, fill=tk.X)

        ttk.Button(left, text=" Calcular Dijkstra", command=self.calcular_dijkstra_ui).pack(fill=tk.X, pady=8)
        ttk.Button(left, text=" Limpiar registro", command=lambda: self.log_text.delete(1.0, tk.END)).pack(fill=tk.X, pady=6)
        ttk.Button(left, text=" Salir", command=self.quit).pack(fill=tk.X, pady=(30,0))

        # Panel derecho: gráfico + log
        right = ttk.Frame(self)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.frame_canvas = ttk.Frame(right)
        self.frame_canvas.pack(fill=tk.BOTH, expand=True)

        self.fig = plt.Figure(figsize=(7,5))
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.frame_canvas)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        ttk.Label(right, text=" Registro (proceso del algoritmo)", font=("Segoe UI", 11, "bold")).pack(anchor=tk.W, pady=(8,0))
        self.log_text = scrolledtext.ScrolledText(right, height=10, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=False, padx=6, pady=4)

    # =====================================================
    # Funciones de interfaz
    # =====================================================
    def generar_grafo_ui(self):
        try:
            n = int(self.spin_n.get())
            if not (8 <= n <= 16):
                messagebox.showwarning("Error", "Ingrese un número entre 8 y 16.")
                return
        except ValueError:
            return
        try:
            nuevo = generar_grafo(n, self.modo_var.get())
        except GrafoNoGenerable as e:
            messagebox.showerror("No se pudo generar el grafo", str(e))
            self.log(f" {e}")
            return
        self.G = nuevo
        self.modo_grafo = self.modo_var.get()
        self.camino_actual = None
        self.distancia_actual = None
        nodos = list(map(str, sorted(self.G.nodes())))
        self.combo_origen['values'] = nodos
        self.combo_destino['values'] = nodos
        self.combo_origen.set(nodos[0])
        self.combo_destino.set(nodos[-1])
        self.log(" Grafo generado correctamente." + (f" Límite de distancia por arista: {DIST_MAX_ARISTA:g}" if self.modo_var.get() != "manual" else ""))
        self.mostrar_grafo_ui()
        if self.modo_grafo == "manual":
            self.ingresar_aristas_manual()   # el grafo (con coordenadas) ya está a la vista

    def ingresar_aristas_manual(self):
        """Abre el diálogo con las aristas actuales (vacío la primera vez). Al aceptar, REEMPLAZA
        el conjunto de aristas por lo escrito; al cancelar, el grafo no cambia."""
        coords = "\n".join(f"Nodo {n}: ({x}, {y})" for n, (x, y) in self.G.nodes(data="pos"))
        actuales = "\n".join(f"{u} {v}" for u, v in self.G.edges())
        texto = DialogoAristas(self, coords, self.G.number_of_nodes(), actuales).resultado
        if texto is None:
            self.log(" Ingreso de aristas cancelado (el grafo no cambió).")
        else:
            self.G.remove_edges_from(list(self.G.edges()))
            nuevas, invalidas = parsear_aristas_manual(texto, self.G)
            self.camino_actual = None       # el camino anterior ya no es válido
            self.distancia_actual = None
            self.log(f" Aristas actualizadas: {self.G.number_of_edges()}")
            if self.modo_grafo != "manual":   # grafo aleatorio: el usuario puede salirse del límite a propósito
                largas = [(u, v) for u, v, w in self.G.edges(data="weight") if w > DIST_MAX_ARISTA]
                if largas:
                    self.log(f" Aviso: {len(largas)} arista(s) superan el límite de distancia ({DIST_MAX_ARISTA:g}) "
                             f"usado en la generación automática: {largas}")
            if invalidas:
                messagebox.showwarning("Líneas ignoradas",
                    f"Se ignoraron {len(invalidas)} línea(s) inválidas (nodos fuera de 0–{self.G.number_of_nodes()-1}, autolazos o formato incorrecto):\n"
                    + "\n".join(invalidas[:10]))
        if self.G.number_of_edges() == 0:
            messagebox.showwarning("Sin aristas", "El grafo no tiene aristas. Pulse «Editar aristas» para ingresarlas o «Generar grafo» para empezar de nuevo.")
        self.mostrar_grafo_ui()

    def editar_aristas_ui(self):
        if not self.G:
            return messagebox.showinfo("Info", "Primero genere un grafo.")
        self.ingresar_aristas_manual()

    def mostrar_grafo_ui(self):
        if not self.G:
            messagebox.showinfo("Info", "Primero genere un grafo.")
            return
        fig = dibujar_grafo(self.G)
        self._render_fig(fig)

    def calcular_dijkstra_ui(self):
        if not self.G:
            return messagebox.showinfo("Info", "Genere primero un grafo.")
        try:
            origen = int(self.combo_origen.get())
            destino = int(self.combo_destino.get())
        except:
            return messagebox.showwarning("Error", "Seleccione origen y destino válidos.")
        if origen == destino:
            return messagebox.showwarning("Error", "El origen y el destino deben ser diferentes.")
        self.log_text.delete(1.0, tk.END)
        start = time.time()
        caminos, dist = dijkstra_detallado(self.G, origen, destino, log_callback=self.log)
        end = time.time()
        if not caminos:
            self.log("\nNo existe camino entre los nodos.")
            return
        self.camino_actual = caminos[0]
        self.distancia_actual = dist
        self.log("\n=== RESULTADO FINAL ===")
        self.log(f"Camino: {' → '.join(map(str, self.camino_actual))}")
        self.log(f"Distancia total: {fmt_peso(self.distancia_actual)}")
        self.log(f"Tiempo de ejecución: {end - start:.5f}s")

        # Mostrar grafo con el camino resaltado
        fig = dibujar_grafo(self.G, camino=self.camino_actual)
        self._render_fig(fig)

    def log(self, text):
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)
        self.update_idletasks()

    def _render_fig(self, fig):
        """Actualiza el gráfico en la interfaz (siempre se ve)."""
        for child in self.frame_canvas.winfo_children():
            child.destroy()
        canvas = FigureCanvasTkAgg(fig, master=self.frame_canvas)
        plt.close(fig)   # libera la figura de pyplot (el canvas conserva su referencia)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.canvas = canvas

# =========================================================
#  EJECUCIÓN
# =========================================================
if __name__ == "__main__":
    app = DijkstraApp()
    app.mainloop()