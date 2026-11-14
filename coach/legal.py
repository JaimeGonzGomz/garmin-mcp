"""Paginas publicas: acerca de (/about) y politica de privacidad (/privacy, /privacidad).

Los datos del responsable se leen del entorno para no publicarlos en el repo:
PRIVACY_CONTROLLER_NAME, PRIVACY_CONTACT_EMAIL, PRIVACY_COUNTRY, PRIVACY_HOSTING (texto libre).
"""
import os
from html import escape

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()
UPDATED = "2026-11-14"

STYLE = """
body{font:16px/1.6 system-ui,sans-serif;max-width:720px;margin:2rem auto;padding:0 1rem;color:#1a1a1a}
h1{font-size:1.6rem}h2{font-size:1.2rem;margin-top:2rem}a{color:#0b5cad}
nav{font-size:.9rem;margin-bottom:1.5rem}.note{background:#f3f4f6;padding:.75rem 1rem;border-radius:6px}
@media(prefers-color-scheme:dark){body{background:#111;color:#e5e5e5}a{color:#6cb2ff}.note{background:#222}}
"""


def _cfg() -> dict[str, str]:
    g = lambda k, d: escape(os.getenv(k) or d)
    return {
        "name": g("PRIVACY_CONTROLLER_NAME", "[PRIVACY_CONTROLLER_NAME sin configurar]"),
        "email": g("PRIVACY_CONTACT_EMAIL", "[PRIVACY_CONTACT_EMAIL sin configurar]"),
        "country": g("PRIVACY_COUNTRY", "Espana"),
        "hosting": g("PRIVACY_HOSTING", "Hetzner Online GmbH"),
    }


def _page(title: str, lang: str, body: str) -> HTMLResponse:
    other = ('<a href="/privacy">English</a>' if lang == "es" else '<a href="/privacidad">Espanol</a>')
    terms = ('<a href="/condiciones">Condiciones</a>' if lang == "es" else '<a href="/terms">Terms</a>')
    priv = ('<a href="/privacidad">Privacidad</a>' if lang == "es" else '<a href="/privacy">Privacy</a>')
    return HTMLResponse(
        f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{title}</title><style>{STYLE}</style></head><body>"
        f'<nav><a href="/about">Garmin Coach</a> · {priv} · {terms} · {other}</nav>{body}</body></html>'
    )


@router.get("/about", response_class=HTMLResponse)
def about():
    return _page("Garmin Coach", "es", """
<h1>Garmin Coach</h1>
<p>Herramienta de entrenamiento de resistencia que permite a una persona consultar sus propios datos de
Garmin Connect (actividades, sueno, VFC, Body Battery, zonas de frecuencia cardiaca) desde Claude, para
preguntar por su entrenamiento y recibir recomendaciones.</p>
<p>El servicio es gratuito y esta en desarrollo. Cada persona solo accede a sus propios datos, y solo despues
de autorizarlo en Garmin. Puede revocar el acceso en cualquier momento.</p>
<p class="note">Garmin Coach es un proyecto independiente, no esta afiliado a Garmin Ltd. ni a Anthropic.
Garmin y Garmin Connect son marcas de Garmin Ltd.</p>
<p><a href="/privacidad">Politica de privacidad</a> · <a href="/condiciones">Condiciones de uso</a></p>""")


@router.get("/privacidad", response_class=HTMLResponse)
def privacidad():
    c = _cfg()
    return _page("Politica de privacidad", "es", f"""
<h1>Politica de privacidad</h1>
<p>Ultima actualizacion: {UPDATED}</p>

<h2>1. Quien es el responsable</h2>
<p>{c['name']} ({c['country']}), persona fisica que opera Garmin Coach sin forma societaria.
Contacto: <a href="mailto:{c['email']}">{c['email']}</a>.</p>

<h2>2. Que datos tratamos</h2>
<p>Solo si conectas tu cuenta de Garmin y tras tu autorizacion, recibimos de Garmin Connect los datos de
tus propios dispositivos: actividades (distancia, ritmo, frecuencia cardiaca, carga y efecto de entrenamiento),
sueno, variabilidad de la frecuencia cardiaca (VFC), Body Battery, estres, frecuencia cardiaca en reposo y
zonas de frecuencia cardiaca. Son datos de salud, una categoria especial segun el RGPD.
Tambien guardamos un identificador de tu cuenta de Garmin y los tokens necesarios para recibir tus datos.
No pedimos ni guardamos tu usuario ni tu contrasena de Garmin.</p>

<h2>3. Para que los usamos y base legal</h2>
<p>Unicamente para ponerlos a tu disposicion a traves del conector de Claude, de modo que tu puedas consultarlos.
No los usamos para publicidad, perfiles, venta ni para entrenar modelos de IA. La base legal es tu
consentimiento explicito (art. 6.1.a y 9.2.a RGPD), que puedes retirar en cualquier momento.</p>

<h2>4. Con quien se comparten</h2>
<ul>
<li><b>Garmin Ltd. / Garmin International:</b> origen de los datos.</li>
<li><b>Proveedor de alojamiento:</b> {c['hosting']} (almacenamiento y ejecucion del servicio).</li>
<li><b>Cloudflare, Inc.:</b> DNS y proteccion del trafico web.</li>
<li><b>Claude (Anthropic):</b> cuando tu, desde claude.ai, usas el conector, tu asistente Claude recibe los datos
que le pides. Ese tratamiento lo decides tu y se rige por la politica de privacidad de Anthropic. Nuestro
servicio no envia tus datos a ningun proveedor de IA por su cuenta.</li>
</ul>
<p>No vendemos ni cedemos tus datos a nadie mas.</p>

<h2>5. Inteligencia artificial</h2>
<p><b>Declaracion de transparencia sobre IA.</b> Los datos de tu cuenta de Garmin los procesa un sistema de inteligencia
artificial, el asistente Claude de Anthropic, unicamente cuando tu se lo pides desde tu cuenta de claude.ai a traves del
conector, para analizar tu entrenamiento y responder a tus preguntas. Antes de conectar te pedimos tu consentimiento
explicito, y puedes retirarlo en cualquier momento desconectando el conector en Claude o escribiendonos.</p>
<p>Nosotros no usamos tus datos de Garmin, ni nada derivado de ellos, para entrenar, evaluar ni mejorar ningun modelo de IA,
ni conservamos tus conversaciones con Claude. Lo que Anthropic haga con tus conversaciones depende de tu cuenta de Claude
y de su politica de privacidad; en los ajustes de privacidad de Claude puedes decidir si se usan para mejorar sus modelos.</p>

<h2>6. Conservacion y borrado</h2>
<p>Conservamos tus datos mientras mantengas conectada tu cuenta. Si la desconectas, o si Garmin nos notifica que
retiraste el acceso, los eliminamos en un maximo de 30 dias. Tambien puedes pedirnos el borrado en cualquier
momento escribiendo al correo de contacto.</p>

<h2>7. Seguridad</h2>
<p>Las comunicaciones usan HTTPS. El acceso a los datos esta restringido a tu propia cuenta y los tokens se
guardan unicamente en nuestro servidor.</p>

<h2>8. Tus derechos</h2>
<p>Puedes ejercer los derechos de acceso, rectificacion, supresion, limitacion, portabilidad y oposicion, y
retirar tu consentimiento, escribiendo a <a href="mailto:{c['email']}">{c['email']}</a>. Si consideras que no
hemos tratado bien tus datos, puedes reclamar ante la Agencia Espanola de Proteccion de Datos
(<a href="https://www.aepd.es">aepd.es</a>).</p>

<h2>9. Cambios</h2>
<p>Si cambiamos esta politica, actualizaremos la fecha y, si el cambio es relevante, te lo comunicaremos.</p>""")


@router.get("/privacy", response_class=HTMLResponse)
def privacy():
    c = _cfg()
    return _page("Privacy policy", "en", f"""
<h1>Privacy policy</h1>
<p>Last updated: {UPDATED}</p>

<h2>1. Who is responsible</h2>
<p>{c['name']} ({c['country']}), an individual operating Garmin Coach without a company.
Contact: <a href="mailto:{c['email']}">{c['email']}</a>.</p>

<h2>2. What data we process</h2>
<p>Only if you connect your Garmin account and after you authorize it, we receive from Garmin Connect the data
from your own devices: activities (distance, pace, heart rate, training load and effect), sleep, heart rate
variability (HRV), Body Battery, stress, resting heart rate and heart rate zones. This is health data, a
special category under the GDPR. We also store an identifier of your Garmin account and the tokens needed to
receive your data. We never ask for or store your Garmin username or password.</p>

<h2>3. Purpose and legal basis</h2>
<p>Solely to make your data available to you through the Claude connector so that you can query it. We do not
use it for advertising, profiling, sale, or to train AI models. The legal basis is your explicit consent
(GDPR Art. 6(1)(a) and 9(2)(a)), which you can withdraw at any time.</p>

<h2>4. Who receives it</h2>
<ul>
<li><b>Garmin Ltd. / Garmin International:</b> source of the data.</li>
<li><b>Hosting provider:</b> {c['hosting']} (storage and running the service).</li>
<li><b>Cloudflare, Inc.:</b> DNS and web traffic protection.</li>
<li><b>Claude (Anthropic):</b> when you use the connector from claude.ai, your Claude assistant receives the data
you ask for. That processing is your choice and is governed by Anthropic's privacy policy. Our service does not
send your data to any AI provider on its own.</li>
</ul>
<p>We do not sell or share your data with anyone else.</p>

<h2>5. Artificial intelligence</h2>
<p><b>AI transparency statement.</b> Your Garmin account data is processed by an artificial intelligence system, the Claude
assistant by Anthropic, only when you ask it from your own claude.ai account through the connector, in order to analyze
your training and answer your questions. Before connecting we ask for your explicit consent, and you can withdraw it at any
time by disconnecting the connector in Claude or by emailing us.</p>
<p>We do not use your Garmin data, or anything derived from it, to train, evaluate or improve any AI model, and we do not
keep your conversations with Claude. What Anthropic does with your conversations depends on your Claude account and its
privacy policy; in Claude's privacy settings you can choose whether they are used to improve its models.</p>

<h2>6. Retention and deletion</h2>
<p>We keep your data while your Garmin account stays connected. If you disconnect it, or Garmin notifies us that
you withdrew access, we delete it within 30 days. You can also request deletion at any time by emailing us.</p>

<h2>7. Security</h2>
<p>Communications use HTTPS. Access is restricted to your own account and tokens are stored only on our
server.</p>

<h2>8. Your rights</h2>
<p>You may exercise your rights of access, rectification, erasure, restriction, portability and objection, and
withdraw consent, by emailing <a href="mailto:{c['email']}">{c['email']}</a>. You may also lodge a complaint
with the Spanish Data Protection Agency (<a href="https://www.aepd.es">aepd.es</a>).</p>

<h2>9. Changes</h2>
<p>If we change this policy we will update the date and, for material changes, notify you.</p>""")


@router.get("/condiciones", response_class=HTMLResponse)
def condiciones():
    c = _cfg()
    return _page("Condiciones de uso", "es", f"""
<h1>Condiciones de uso</h1>
<p>Ultima actualizacion: {UPDATED}</p>

<h2>1. El servicio</h2>
<p>Garmin Coach es un conector gratuito que permite a una persona consultar sus propios datos de Garmin Connect desde su
asistente de IA (Claude). Lo opera {c['name']} ({c['country']}), persona fisica. Es un proyecto independiente, no afiliado
a Garmin Ltd. ni a Anthropic.</p>

<h2>2. Uso permitido</h2>
<p>Solo puedes conectar tu propia cuenta de Garmin y consultar tus propios datos, para uso personal. No puedes intentar
acceder a datos de otras personas, eludir las medidas de seguridad, usar el servicio para fines ilegales ni de forma que
sobrecargue o abuse de el. Podemos suspender el acceso de quien incumpla estas condiciones.</p>

<h2>3. No es consejo medico</h2>
<p>La informacion y las sugerencias de entrenamiento son orientativas y no sustituyen a un profesional sanitario. No uses
el servicio en situaciones en las que pueda estar en juego la vida o la salud. Ante dolor, mareo u otros sintomas, para y
consulta a un profesional. Entrenas bajo tu propia responsabilidad.</p>

<h2>4. Datos de Garmin y garantias</h2>
<p>Los datos provienen de Garmin Connect y se ofrecen "tal cual", sin garantia de exactitud, disponibilidad ni
continuidad. El servicio puede interrumpirse o cambiar. Si envias un entreno a tu dispositivo, revisalo antes de usarlo.
Garmin y sus sociedades afiliadas no son responsables del servicio, de los datos que se muestran en el ni de su uso, y se
benefician de las limitaciones de responsabilidad de esta clausula.</p>

<h2>5. Limitacion de responsabilidad</h2>
<p>En la medida en que lo permita la ley, no respondemos de danos indirectos ni de perdidas derivadas del uso del servicio,
y nuestra responsabilidad total se limita a lo que hayas pagado por el, que es cero. Esto no afecta a los derechos que la ley
reconozca irrenunciablemente a los consumidores.</p>

<h2>6. Tus datos y tu privacidad</h2>
<p>El tratamiento de tus datos se describe en la <a href="/privacidad">politica de privacidad</a>. Puedes desconectar tu
cuenta y pedir el borrado de tus datos en cualquier momento.</p>

<h2>7. Informar de abusos y contacto</h2>
<p>Para informar de un abuso o un problema de seguridad, o para cualquier consulta, escribe a
<a href="mailto:{c['email']}">{c['email']}</a>.</p>

<h2>8. Cambios y ley aplicable</h2>
<p>Podemos modificar estas condiciones; la fecha de arriba indica la ultima version. Se rigen por la ley espanola, sin
perjuicio de la proteccion que te corresponda como consumidor en tu pais de residencia.</p>""")


@router.get("/terms", response_class=HTMLResponse)
def terms():
    c = _cfg()
    return _page("Terms of use", "en", f"""
<h1>Terms of use</h1>
<p>Last updated: {UPDATED}</p>

<h2>1. The service</h2>
<p>Garmin Coach is a free connector that lets an individual query their own Garmin Connect data from their AI assistant
(Claude). It is operated by {c['name']} ({c['country']}), an individual. It is an independent project, not affiliated with
Garmin Ltd. or Anthropic.</p>

<h2>2. Permitted use</h2>
<p>You may only connect your own Garmin account and query your own data, for personal use. You may not try to access other
people's data, bypass security measures, use the service for unlawful purposes or in a way that overloads or abuses it. We may
suspend access for anyone who breaches these terms.</p>

<h2>3. Not medical advice</h2>
<p>Training information and suggestions are indicative and do not replace a health professional. Do not use the service
where life or health may be at stake. If you feel pain, dizziness or other symptoms, stop and consult a professional. You
train at your own risk.</p>

<h2>4. Garmin data and warranties</h2>
<p>Data comes from Garmin Connect and is provided "as is", without warranty of accuracy, availability or continuity. The
service may be interrupted or change. If you send a workout to your device, review it before using it. Garmin and its
affiliates are not responsible for the service, the data shown in it or its use, and benefit from the limitations of liability
in this clause.</p>

<h2>5. Limitation of liability</h2>
<p>To the extent permitted by law, we are not liable for indirect damages or losses arising from use of the service, and our
total liability is limited to what you paid for it, which is zero. This does not affect rights that the law grants to
consumers and that cannot be waived.</p>

<h2>6. Your data and privacy</h2>
<p>How we process your data is described in the <a href="/privacy">privacy policy</a>. You can disconnect your account and
request deletion of your data at any time.</p>

<h2>7. Reporting abuse and contact</h2>
<p>To report abuse or a security issue, or for any question, email <a href="mailto:{c['email']}">{c['email']}</a>.</p>

<h2>8. Changes and governing law</h2>
<p>We may change these terms; the date above shows the latest version. They are governed by Spanish law, without prejudice to
the protection you have as a consumer in your country of residence.</p>""")
