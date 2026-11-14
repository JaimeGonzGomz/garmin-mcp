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
    return HTMLResponse(
        f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{title}</title><style>{STYLE}</style></head><body>"
        f'<nav><a href="/about">Garmin Coach</a> · {other}</nav>{body}</body></html>'
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
<p><a href="/privacidad">Politica de privacidad</a></p>""")


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

<h2>5. Conservacion y borrado</h2>
<p>Conservamos tus datos mientras mantengas conectada tu cuenta. Si la desconectas, o si Garmin nos notifica que
retiraste el acceso, los eliminamos en un maximo de 30 dias. Tambien puedes pedirnos el borrado en cualquier
momento escribiendo al correo de contacto.</p>

<h2>6. Seguridad</h2>
<p>Las comunicaciones usan HTTPS. El acceso a los datos esta restringido a tu propia cuenta y los tokens se
guardan unicamente en nuestro servidor.</p>

<h2>7. Tus derechos</h2>
<p>Puedes ejercer los derechos de acceso, rectificacion, supresion, limitacion, portabilidad y oposicion, y
retirar tu consentimiento, escribiendo a <a href="mailto:{c['email']}">{c['email']}</a>. Si consideras que no
hemos tratado bien tus datos, puedes reclamar ante la Agencia Espanola de Proteccion de Datos
(<a href="https://www.aepd.es">aepd.es</a>).</p>

<h2>8. Cambios</h2>
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

<h2>5. Retention and deletion</h2>
<p>We keep your data while your Garmin account stays connected. If you disconnect it, or Garmin notifies us that
you withdrew access, we delete it within 30 days. You can also request deletion at any time by emailing us.</p>

<h2>6. Security</h2>
<p>Communications use HTTPS. Access is restricted to your own account and tokens are stored only on our
server.</p>

<h2>7. Your rights</h2>
<p>You may exercise your rights of access, rectification, erasure, restriction, portability and objection, and
withdraw consent, by emailing <a href="mailto:{c['email']}">{c['email']}</a>. You may also lodge a complaint
with the Spanish Data Protection Agency (<a href="https://www.aepd.es">aepd.es</a>).</p>

<h2>8. Changes</h2>
<p>If we change this policy we will update the date and, for material changes, notify you.</p>""")
