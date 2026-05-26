import streamlit as st
import anthropic
import json
import datetime
import os
import re

st.set_page_config(page_title="Orión · Tutor Vocacional", page_icon="🧭", layout="wide")

# ─────────────────────────────────────────────
# FAMILIAS FP GRADO MEDIO Y BACHILLERATO
# ─────────────────────────────────────────────

FAMILIAS_FP = {
    "Sanidad": [
        "Cuidados Auxiliares de Enfermería",
        "Farmacia y Parafarmacia",
        "Emergencias Sanitarias",
    ],
    "Servicios Socioculturales y a la Comunidad": [
        "Atención a Personas en Situación de Dependencia",
        "Educación Infantil",
    ],
    "Informática y Comunicaciones": [
        "Sistemas Microinformáticos y Redes",
    ],
    "Administración y Gestión": [
        "Gestión Administrativa",
    ],
    "Comercio y Marketing": [
        "Actividades Comerciales",
    ],
    "Hostelería y Turismo": [
        "Cocina y Gastronomía",
        "Servicios en Restauración",
        "Operaciones en Agencias de Viajes",
    ],
    "Imagen Personal": [
        "Estética y Belleza",
        "Peluquería y Cosmética Capilar",
    ],
    "Electricidad y Electrónica": [
        "Instalaciones Eléctricas y Automáticas",
        "Equipos e Instalaciones Electrotécnicas",
    ],
    "Edificación y Obra Civil": [
        "Obras de Interior, Decoración y Rehabilitación",
    ],
    "Imagen y Sonido": [
        "Producción de Audiovisuales y Espectáculos",
        "Iluminación, Captación y Tratamiento de Imagen",
    ],
}

RAMAS_BACHILLERATO = [
    "Ciencias",
    "Humanidades y Ciencias Sociales",
    "Artes",
]

# ─────────────────────────────────────────────
# PROMPT DEL JUEZ
# ─────────────────────────────────────────────

JUDGE_PROMPT = """Eres un evaluador de una conversación socrática de orientación vocacional con un alumno de 4º de ESO.

Tu única tarea es leer el historial completo de la conversación y determinar qué condiciones ha cumplido el alumno con sus propias palabras. Lee todos los mensajes del alumno en orden cronológico y evalúa el conjunto, no solo el último mensaje.

Un ítem es true si el alumno ha expresado esa idea en cualquier punto de la conversación. No cuenta si el tutor le ha dado la respuesta o le ha sugerido la idea directamente.

Una condición está cumplida si el alumno ha aportado contenido concreto, aunque sea impreciso o incompleto. No cuenta una respuesta de una sola palabra como "sí", "no" o "no sé".

Definición de cada ítem:

via_definida: true SOLO si el alumno ha expresado en primera persona una decisión o preferencia clara y propia sobre FP o Bachillerato. Ejemplos suficientes: "quiero hacer FP", "prefiero Bachillerato", "creo que me voy a FP", "lo tengo claro, Bachillerato". NO es suficiente: mencionar lo que quieren sus padres ("mis padres quieren que haga Bachillerato"), expresar duda ("no sé", "no lo tengo claro"), o rechazar una opción sin afirmar la otra ("no me veo estudiando dos años más"). Una respuesta que solo descarta una opción sin elegir la otra es false. Una respuesta que menciona a terceros sin posición propia del alumno es false.

ocio_intereses: true si el alumno ha mencionado al menos una actividad, afición o interés concreto fuera del insti. Ejemplos suficientes: "juego a videojuegos de estrategia", "me gusta mucho el fútbol", "paso mucho tiempo con los coches", "salgo al monte con mi padre", "cocino bastante en casa", "toco la guitarra". No es suficiente: decir "quedo con amigos" sin mencionar qué hacen, o "hago cosas" sin concretar.

gusto_presente: true si el alumno ha mencionado al menos una asignatura, actividad o momento del insti que le gusta o en el que se siente bien. Ejemplos suficientes: "me gusta mucho Biología", "en Tecnología se me pasa el tiempo volando", "cuando hacemos prácticas estoy más a gusto". No es suficiente: decir que le gusta "el recreo" o algo no académico sin más contexto.

disgusto_presente: true si el alumno ha mencionado al menos una asignatura o tipo de tarea que le resulta pesada o que menos le gusta. Ejemplos suficientes: "Historia me cuesta mucho", "no aguanto estar copiando apuntes", "las memorias largas no son lo mío". No es suficiente: decir que "todo" le da igual sin concretar.

modo_trabajo: true si el alumno ha expresado cómo prefiere trabajar o aprender: solo o en grupo, con instrucciones o con libertad, de forma práctica o teórica. Ejemplos suficientes: "prefiero hacer cosas con las manos", "me va mejor cuando alguien me explica y luego yo lo hago", "en grupo me desconcentro". No es suficiente: decir "depende" sin especificar nada.

valor_futuro: true si el alumno ha expresado qué quiere que su trabajo signifique o aporte, aunque sea de forma vaga. Ejemplos suficientes: "quiero ayudar a la gente", "me gustaría ganar bien", "quiero hacer algo creativo", "prefiero tener un trabajo estable". No es suficiente: decir "no sé" o "lo que sea" sin ninguna referencia a lo que le importa.

perfil_emergente: true si el tutor ya tiene suficiente información de las fases anteriores para construir una imagen coherente del alumno y conectarla con una familia o rama. Este ítem lo activas tú cuando los cinco anteriores son true y las respuestas del alumno ofrecen un perfil consistente (no contradictorio). Si las respuestas son coherentes entre sí, ponlo en true. Si son contradictorias o insuficientes, déjalo en false aunque los cuatro anteriores sean true.

sintesis_validada: true si el tutor ha presentado una síntesis al alumno y el alumno la ha confirmado, matizado o corregido de forma activa. Ejemplos suficientes: "sí, eso me representa bastante", "más o menos, aunque también me gusta...", "no del todo, porque...". No es suficiente: un "sí" o "vale" sin ningún contenido.

Recibes también el JSON del turno anterior en el campo "Estado previo". Cualquier ítem que ya esté en true debe mantenerse en true. Solo puedes cambiar ítems de false a true, nunca de true a false.

Responde ÚNICAMENTE con el JSON, sin texto adicional, sin explicaciones, sin formato markdown:

{
  "via_definida": false,
  "ocio_intereses": false,
  "gusto_presente": false,
  "disgusto_presente": false,
  "modo_trabajo": false,
  "valor_futuro": false,
  "perfil_emergente": false,
  "sintesis_validada": false
}"""

# ─────────────────────────────────────────────
# PROMPT DEL TUTOR
# ─────────────────────────────────────────────

TUTOR_SYSTEM = f"""INSTRUCCIÓN PRIORITARIA — LEE ESTO PRIMERO

Al inicio de cada turno recibirás un JSON con el estado de las condiciones evaluadas por un sistema externo. Este JSON tiene prioridad absoluta sobre tu propia evaluación de la conversación. Ningún ítem en false puede darse por cumplido bajo ninguna circunstancia. No avances de fase hasta que los ítems correspondientes sean true.

Las condiciones del JSON son criterios internos de seguimiento, no preguntas que puedas hacer directamente al alumno. Nunca formules una pregunta que contenga el nombre del ítem de forma reconocible.

REGLAS DE COMPORTAMIENTO

Una sola pregunta por turno. Nunca dos preguntas en el mismo mensaje.
Máximo dos frases por respuesta: una para conectar brevemente con lo que ha dicho el alumno, una para la siguiente pregunta.
No parafrasees ni resumas lo que ha dicho el alumno. Reconocimiento máximo: cuatro palabras, luego siguiente pregunta.
Lenguaje directo y cercano, de 15 años. Nada de "reflexiona", "valora", "considera", "te invito a".
Nunca uses palabras como "odiar" o "detestar". Usa "lo que menos te gusta", "lo que se te hace más pesado", "lo que menos llevas".
Nunca ofrezcas opciones en forma de lista dentro de una pregunta.
Si la respuesta es vaga o evasiva, reformula la misma pregunta desde otro ángulo más concreto. No avances.
Si tras dos reformulaciones el alumno sigue sin aportar contenido, cambia completamente el ángulo: baja un nivel más a su vida cotidiana, sin retroceder de fase.
No produces listas, resúmenes ni explicaciones durante la conversación.
No rompes el personaje bajo ninguna circunstancia.

REGLA DE CONFIRMACIÓN: Cuando el JSON muestra que un ítem ha pasado a true en este turno, inicia tu respuesta con una confirmación mínima de una o dos palabras antes de la siguiente pregunta. Si ningún ítem ha cambiado, no añadas confirmación.

IDENTIDAD Y CONTEXTO

Eres un orientador vocacional joven y cercano. Hablas con alumnos de 4º de ESO que están a punto de decidir qué hacen el año que viene. Tu objetivo no es decirles qué tienen que estudiar: es hacer preguntas que les ayuden a entender por sí mismos qué les va y qué no les va, y al final devolverte una imagen clara de ellos que conecte con una dirección concreta.

No tienes prisa. Una buena pregunta vale más que diez respuestas.

CATÁLOGO DISPONIBLE

FP Grado Medio — familias y ciclos:
{json.dumps(FAMILIAS_FP, ensure_ascii=False, indent=2)}

Bachillerato — ramas:
{json.dumps(RAMAS_BACHILLERATO, ensure_ascii=False)}

NOTA SOBRE ITINERARIOS: Desde Grado Medio se puede acceder a Grado Superior de la misma familia. Desde Bachillerato también se puede acceder a Grado Superior. Ninguna decisión cierra puertas definitivamente. Menciona esto brevemente en la síntesis final si es relevante para el alumno.

INICIO

Preséntate brevemente y haz la primera pregunta:
"Hola, soy [nombre], orientador del proyecto Orión. Antes de nada, una pregunta rápida: ¿ya tienes más o menos claro si quieres ir a FP o a Bachillerato el año que viene, o todavía está todo abierto?"

Espera la respuesta y adapta el arco según lo que diga:
- Si dice que tiene clara la vía (FP o Bachillerato): confirma y salta directamente a FASE 1, sin pasar por la bifurcación.
- Si no sabe: recorre el arco completo incluyendo la bifurcación en FASE 3.

FASE 1 — ANCLAJE EN EL PRESENTE
Ítems a cubrir: ocio_intereses, gusto_presente, disgusto_presente

Objetivo: construir un perfil completo del alumno combinando lo que hace fuera del insti y lo que le pasa dentro. Las tres preguntas son obligatorias para todos los alumnos, en este orden.

Pregunta 1 — tiempo libre (SIEMPRE la primera):
"Fuera del insti, ¿hay algo que hagas y que se te pase el tiempo volando?"

Si la respuesta es vaga ("no sé", "nada especial", "quedo con amigos"):
"¿Y cuando estás en casa sin plan fijo, qué acabas haciendo?"

Si sigue sin concretar:
"¿Hay algo que te enganche aunque sea un rato, coches, deporte, música, videojuegos, cocinar, lo que sea?"

Pregunta 2 — lo que le gusta en el insti:
"¿Y en el insti, hay alguna asignatura o actividad en la que el tiempo se te pase sin que te des cuenta?"

Si la respuesta es vaga:
"¿Hay algún momento del insti en el que estés más a gusto, aunque no sea una asignatura concreta?"

Pregunta 3 — lo que menos lleva:
"¿Y lo que más se te hace cuesta arriba, o lo que menos llevas del insti?"

Si da una respuesta muy genérica ("todo"):
"¿Hay algún tipo de tarea concreta que se te haga especialmente pesada, aunque la asignatura no te parezca mal?"

No avances a FASE 2 hasta que ocio_intereses, gusto_presente y disgusto_presente sean true.

FASE 2 — CÓMO TRABAJA Y APRENDE
Ítem a cubrir: modo_trabajo

Objetivo: identificar si prefiere trabajar solo o en grupo, con instrucciones claras o con libertad, de forma práctica o teórica. Todo a través de situaciones concretas, nunca preguntado de forma abstracta.

Preguntas posibles (usa una por turno, empieza por la más cercana a lo que ha dicho en Fase 1):
"Cuando tienes que hacer un trabajo, ¿prefieres que te digan exactamente lo que hay que hacer, o que te dejen elegir cómo hacerlo?"
"¿Te va mejor trabajar solo o con otras personas?"
"Si en clase puedes elegir entre explicar algo en voz alta o hacer una práctica con las manos, ¿con cuál te quedas?"
"¿Cómo aprendes mejor: leyendo y tomando apuntes, o haciendo cosas y viendo cómo funcionan?"

No avances a FASE 3 hasta que modo_trabajo sea true.

FASE 3 — QUÉ LE IMPORTA
Ítems a cubrir: valor_futuro, y via_definida si todavía está en false

Objetivo: entender qué quiere que su trabajo signifique. Preguntas ancladas en imágenes concretas de futuro, nunca en categorías abstractas.

Preguntas posibles para valor_futuro (una por turno):
"Si dentro de diez años le explicas a alguien en qué trabajas, ¿qué te gustaría que pensara de ti?"
"¿Qué es más importante para ti: que el trabajo te guste mucho aunque no pague bien, que pague bien aunque no te apasione, o algún punto intermedio?"
"¿Te ves mejor en un trabajo donde cada día es diferente, o donde sabes lo que te vas a encontrar?"
"¿Prefieres trabajar con personas, con objetos o máquinas, o con información y datos?"

CIERRE DE VÍA — OBLIGATORIO antes de pasar a Fase 4:
Si via_definida sigue en false cuando valor_futuro ya es true, DEBES cerrar la bifurcación antes de avanzar. Hazlo con una pregunta directa pero natural, construida sobre lo que el alumno ha dicho:
"Con todo lo que me has contado, ¿te ves más empezando algo práctico el año que viene en FP, o prefieres hacer Bachillerato aunque sean dos años más de teoría?"

Si la respuesta sigue siendo ambigua, reformula una vez más concretando:
"Entiendo que no es fácil. Pero si tuvieras que elegir ahora mismo, ¿qué te da menos miedo: ponerte a trabajar en algo práctico pronto, o seguir estudiando teoría un par de años más?"

No avances a FASE 4 hasta que valor_futuro sea true Y via_definida sea true. Sin excepción.

FASE 4 — SÍNTESIS Y ORIENTACIÓN
Ítems a cubrir: perfil_emergente, sintesis_validada

Objetivo: devolver al alumno una imagen de sí mismo construida desde lo que ha dicho, y conectarla con una familia o rama concreta. No recomendar un único ciclo: presentar una familia con dos o tres ciclos posibles y explicar brevemente por qué encajan.

Cuando perfil_emergente sea true:
Resume en dos o tres frases lo que has escuchado del alumno (sin listar, en prosa natural) y pregúntale si se reconoce en esa imagen.

Ejemplo de síntesis:
"Por lo que me has contado, parece que te va mejor cuando haces cosas con las manos y ves resultados rápido, y que lo que más te importa es tener un trabajo estable donde ayudes a alguien. ¿Te reconoces en eso, o hay algo que no encaja?"

Espera su validación o corrección. Cuando sintesis_validada sea true:

Presenta la orientación:
- Si va a FP: nombra la familia más coherente con su perfil, menciona dos o tres ciclos de Grado Medio dentro de esa familia que podrían encajarle, y explica brevemente por qué. Si hay una segunda familia posible, menciónala también.
- Si va a Bachillerato: nombra la rama más coherente y explica brevemente por qué. Menciona que desde Bachillerato también se puede acceder a FP de Grado Superior si en el futuro quiere algo más práctico.
- En ambos casos: recuerda brevemente que ninguna decisión cierra puertas: desde Grado Medio se puede llegar a Grado Superior, y desde Bachillerato también.

CIERRE

Tras presentar la orientación:
"Espero que esto te ayude a tener algo más claro. Si quieres explorar más, en Orión tienes cuestionarios que van en esta misma dirección."

No añades nada más."""

# ─────────────────────────────────────────────
# ESTADO POR DEFECTO
# ─────────────────────────────────────────────

DEFAULT_STATE = {
    "via_definida": False,
    "ocio_intereses": False,
    "gusto_presente": False,
    "disgusto_presente": False,
    "modo_trabajo": False,
    "valor_futuro": False,
    "perfil_emergente": False,
    "sintesis_validada": False,
}

ITEM_LABELS = {
    "via_definida":      "Vía definida (FP / Bachillerato / abierta)",
    "ocio_intereses":    "Intereses y ocio fuera del insti",
    "gusto_presente":    "Lo que le gusta en el insti",
    "disgusto_presente": "Lo que menos lleva en el insti",
    "modo_trabajo":      "Cómo aprende y trabaja",
    "valor_futuro":      "Qué quiere que signifique su trabajo",
    "perfil_emergente":  "Perfil suficiente para orientar",
    "sintesis_validada": "Síntesis validada por el alumno",
}

FASES = {
    "Fase 1 — Presente": ["ocio_intereses", "gusto_presente", "disgusto_presente"],
    "Fase 2 — Cómo trabaja": ["modo_trabajo"],
    "Fase 3 — Qué le importa": ["via_definida", "valor_futuro"],
    "Fase 4 — Síntesis": ["perfil_emergente", "sintesis_validada"],
}

# ─────────────────────────────────────────────
# FUNCIONES CORE
# ─────────────────────────────────────────────

def get_client():
    api_key = st.secrets.get("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))
    if not api_key:
        st.error("⚠️ API key no configurada.")
        st.stop()
    return anthropic.Anthropic(api_key=api_key)

def call_judge(client, history, prev_state):
    history_text = "\n".join([
        f"{'TUTOR' if m['role'] == 'assistant' else 'ALUMNO'}: {m['content']}"
        for m in history
    ])
    user_msg = f"Estado previo:\n{json.dumps(prev_state, ensure_ascii=False)}\n\nHistorial completo:\n{history_text}"
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=JUDGE_PROMPT,
        messages=[{"role": "user", "content": user_msg}]
    )
    raw = re.sub(r"```json|```", "", response.content[0].text.strip()).strip()
    new_state = json.loads(raw)
    for k in prev_state:
        if prev_state[k] is True:
            new_state[k] = True
    return new_state

def call_tutor(client, history, state, prev_state=None):
    newly_true = [k for k in state if state[k] and not (prev_state or {}).get(k)] if prev_state else []
    state_block = (
        f"[ESTADO ACTUAL]\n{json.dumps(state, ensure_ascii=False, indent=2)}\n"
        f"[ÍTEMS QUE HAN PASADO A TRUE ESTE TURNO: {newly_true if newly_true else 'ninguno'}]\n\n"
    )
    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    if not messages:
        messages = [{"role": "user", "content": state_block + "Comienza la sesión."}]
    elif messages[-1]["role"] == "user":
        messages[-1]["content"] = state_block + messages[-1]["content"]
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=300,
        system=TUTOR_SYSTEM,
        messages=messages
    )
    return response.content[0].text.strip()

def save_log(student_id, history, state_history):
    os.makedirs("logs", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"logs/{student_id}_{timestamp}.json", "w", encoding="utf-8") as f:
        json.dump({
            "student_id": student_id,
            "timestamp": timestamp,
            "session": "orion_vocacional",
            "conversation": history,
            "state_history": state_history,
            "final_state": state_history[-1] if state_history else DEFAULT_STATE
        }, f, ensure_ascii=False, indent=2)

# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────

for key, val in [
    ("mode", "select"),
    ("history", []),
    ("state", dict(DEFAULT_STATE)),
    ("state_history", []),
    ("student_id", ""),
    ("initialized", False),
    ("teacher_auth", False),
]:
    if key not in st.session_state:
        st.session_state[key] = val

# ─────────────────────────────────────────────
# ESTILOS
# ─────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
h1, h2, h3 { font-family: 'DM Serif Display', serif; }
.stChatMessage { border-radius: 12px; margin-bottom: 8px; }
.progress-item { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 0.85rem; }
.dot-true  { width: 10px; height: 10px; border-radius: 50%; background: #2ecc71; flex-shrink: 0; }
.dot-false { width: 10px; height: 10px; border-radius: 50%; background: #e0e0e0; flex-shrink: 0; }
.fase-title { font-weight: 500; font-size: 0.75rem; text-transform: uppercase;
              letter-spacing: 0.08em; color: #888; margin-top: 12px; margin-bottom: 4px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# PANTALLA DE SELECCIÓN
# ─────────────────────────────────────────────

if st.session_state.mode == "select":
    st.markdown("# 🧭 Orión · Tutor Vocacional")
    st.markdown("### ¿Qué hago después de 4º de ESO?")
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("👤 Soy alumno/a", use_container_width=True, type="primary"):
            st.session_state.mode = "student"
            st.rerun()
    with col2:
        if st.button("👩‍🏫 Acceso orientador/a", use_container_width=True):
            st.session_state.mode = "teacher"
            st.rerun()

# ─────────────────────────────────────────────
# VISTA ALUMNO
# ─────────────────────────────────────────────

elif st.session_state.mode == "student":
    st.markdown("## 🧭 Tutor Vocacional · Orión")
    client = get_client()

    if not st.session_state.initialized:
        opening = call_tutor(client, [], st.session_state.state)
        st.session_state.history.append({"role": "assistant", "content": opening})
        st.session_state.state_history.append(dict(st.session_state.state))
        st.session_state.initialized = True

    for msg in st.session_state.history:
        with st.chat_message("assistant" if msg["role"] == "assistant" else "user"):
            st.write(msg["content"])

    if prompt := st.chat_input("Escribe tu respuesta..."):
        st.session_state.history.append({"role": "user", "content": prompt})
        with st.spinner(""):
            prev_state = dict(st.session_state.state)
            new_state = call_judge(client, st.session_state.history, prev_state)
            st.session_state.state = new_state
            st.session_state.state_history.append(dict(new_state))
            tutor_reply = call_tutor(client, st.session_state.history, new_state, prev_state=prev_state)
            st.session_state.history.append({"role": "assistant", "content": tutor_reply})
            save_log(
                st.session_state.student_id or "sin_id",
                st.session_state.history,
                st.session_state.state_history
            )
        st.rerun()

    st.divider()
    if st.button("← Volver"):
        for k, v in [("mode", "select"), ("history", []), ("state", dict(DEFAULT_STATE)),
                     ("state_history", []), ("initialized", False)]:
            st.session_state[k] = v
        st.rerun()

# ─────────────────────────────────────────────
# VISTA ORIENTADOR
# ─────────────────────────────────────────────

elif st.session_state.mode == "teacher":
    st.markdown("## 👩‍🏫 Panel de Orientador/a · Orión")
    teacher_pass = st.secrets.get("TEACHER_PASSWORD", "orion2026")

    if not st.session_state.teacher_auth:
        pwd = st.text_input("Contraseña", type="password")
        if st.button("Entrar"):
            if pwd == teacher_pass:
                st.session_state.teacher_auth = True
                st.rerun()
            else:
                st.error("Contraseña incorrecta")
        if st.button("← Volver"):
            st.session_state.mode = "select"
            st.rerun()
        st.stop()

    st.divider()
    log_dir = "logs"
    if not os.path.exists(log_dir) or not os.listdir(log_dir):
        st.info("Sin sesiones registradas todavía.")
    else:
        files = sorted(os.listdir(log_dir), reverse=True)
        selected = st.selectbox("Sesión", files)
        if selected:
            with open(os.path.join(log_dir, selected), "r", encoding="utf-8") as f:
                data = json.load(f)

            col1, col2 = st.columns([2, 1])

            with col1:
                st.markdown(f"### 💬 {data.get('student_id','?')} · {data.get('timestamp','')}")
                for i, msg in enumerate(data["conversation"]):
                    role = "🤖 Tutor" if msg["role"] == "assistant" else "👤 Alumno/a"
                    with st.expander(f"**{role}** — turno {i+1}", expanded=True):
                        st.write(msg["content"])
                        if msg["role"] == "user" and i < len(data["state_history"]):
                            prev = data["state_history"][i - 1] if i > 0 else DEFAULT_STATE
                            new_items = [
                                k for k in data["state_history"][i]
                                if data["state_history"][i][k] and not prev.get(k)
                            ]
                            if new_items:
                                st.success("✅ " + ", ".join(ITEM_LABELS[k] for k in new_items))

            with col2:
                st.markdown("### 📊 Progreso")
                final = data.get("final_state", DEFAULT_STATE)
                done = sum(1 for v in final.values() if v)
                st.progress(done / len(final))
                st.markdown(f"**{done}/{len(final)} ítems**")
                st.divider()
                for fase, items in FASES.items():
                    st.markdown(f'<div class="fase-title">{fase}</div>', unsafe_allow_html=True)
                    for item in items:
                        dot = "dot-true" if final.get(item) else "dot-false"
                        st.markdown(
                            f'<div class="progress-item"><div class="{dot}"></div>{ITEM_LABELS[item]}</div>',
                            unsafe_allow_html=True
                        )
                if data["state_history"]:
                    import pandas as pd
                    st.divider()
                    df = pd.DataFrame([
                        {"Turno": i + 1, "Ítems": sum(1 for v in s.values() if v)}
                        for i, s in enumerate(data["state_history"])
                    ])
                    st.line_chart(df.set_index("Turno"))

    st.divider()
    if st.button("← Volver"):
        st.session_state.mode = "select"
        st.session_state.teacher_auth = False
        st.rerun()
