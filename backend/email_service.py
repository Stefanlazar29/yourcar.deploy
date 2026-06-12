import os, httpx
from datetime import datetime


RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FROM_EMAIL = "support@mulberry.autos"
BASE_URL = "https://api.resend.com/emails"

def _send(to: str, subject: str, html: str):
    key = os.getenv("RESEND_API_KEY") or RESEND_API_KEY
    if not key:
        return
    try:
        httpx.post(BASE_URL, headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }, json={"from": FROM_EMAIL, "to": [to], "subject": subject, "html": html}, timeout=10)
    except Exception as e:
        print(f"[EmailService] Failed to send email to: {e}")


def _rows(*pairs) -> str:
    out = ""
    for i, (label, value, highlight) in enumerate(pairs):
        bg = "background:#fafafa;" if i % 2 == 0 else ""
        color = "#0a0a0a" if not highlight else "#000"
        fw = "700" if highlight else "400"
        border = "border-bottom:1px solid #f0f0f0;"
        out += f"""
        <tr style="{bg}{border}">
            <td style="padding:14px 20px;font-size:13px;color:#888;width:45%">{label}</td>
            <td style="padding:14px 20px;font-size:13px;font-weight:{fw};color:{color};text-align:right">{value}</td>
        </tr>
        """
    return out

def _base(badge: str, title: str, subtitle: str, rows_html: str, cta_label: str = "Deschide Mulberry →", cta_url: str = "https://mulberry.autos/mulberry_app.html", extra_block: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="ro">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f4f4f4;font-family:'Helvetica Neue',Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4;padding:32px 0">
<tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08)">

  <!-- HEADER -->
  <tr>
    <td style="padding:0;margin:0">
      <img src="https://mulberry.autos/assets/mulberry-email-header.png" width="560" style="display:block;width:100%;max-width:560px;border-radius:16px 16px 0 0" alt="Mulberry">
    </td>
  </tr>

  <!-- BODY -->
  <tr>
    <td style="padding:36px 40px">

      <!-- Badge -->
      <div style="display:inline-block;background:#0a0a0a;color:#E1FF00;font-size:11px;font-weight:800;padding:5px 14px;border-radius:20px;letter-spacing:1px;margin-bottom:18px">{badge}</div>

      <!-- Title -->
      <div style="font-size:23px;font-weight:800;color:#0a0a0a;margin-bottom:6px;line-height:1.2">{title}</div>
      <div style="font-size:14px;color:#777;margin-bottom:28px;line-height:1.6">{subtitle}</div>

      <!-- Data table -->
      <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #ebebeb;border-radius:12px;overflow:hidden;margin-bottom:28px">
        {rows_html}
      </table>

      {extra_block}

      <!-- CTA -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px">
        <tr>
          <td align="center">
            <a href="{cta_url}" style="display:inline-block;background:#0a0a0a;color:#E1FF00;text-decoration:none;padding:15px 48px;border-radius:10px;font-weight:800;font-size:15px;letter-spacing:0.3px">{cta_label}</a>
          </td>
        </tr>
      </table>

      <!-- Note -->
      <div style="font-size:12px;color:#bbb;text-align:center;line-height:1.7">
        Ai primit acest email deoarece ești înregistrat pe <strong style="color:#0a0a0a">mulberry.autos</strong>.<br>
        Dacă nu recunoști această activitate, <a href="mailto:support@mulberry.autos" style="color:#0a0a0a">contactează-ne imediat</a>.
      </div>

    </td>
  </tr>

  <!-- FOOTER -->
  <tr>
    <td style="background:#f9f9f9;padding:22px 40px;border-top:1px solid #f0f0f0;text-align:center">
      <div style="font-size:11px;color:#aaa;line-height:1.9">
        © 2026 Mulberry Autos SRL &nbsp;·&nbsp;
        <a href="mailto:support@mulberry.autos" style="color:#888;text-decoration:none">support@mulberry.autos</a> &nbsp;·&nbsp;
        <a href="https://mulberry.autos" style="color:#888;text-decoration:none">mulberry.autos</a>
      </div>
    </td>
  </tr>

</table>
</td></tr>
</table>
</body>
</html>"""

# ── EMAIL TYPES ───────────────────────────────────────────────────────────────

def send_welcome(to: str, name: str, vin: str = "", plate: str = "", model_vehicle: str = "", k_code: str = ""):
    html = f"""<html dir="ltr" lang="en"><head></head><body style="background-color:#ffffff"><table border="0" width="100%" cellpadding="0" cellspacing="0" role="presentation" align="center"><tbody><tr><td style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Roboto','Oxygen','Ubuntu','Cantarell','Fira Sans','Droid Sans','Helvetica Neue',sans-serif;font-size:1em;min-height:100%;line-height:155%;background-color:#ffffff"><table align="center" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="max-width:600px;width:100%;color:#000000;background-color:#ffffff;border-radius:0px;line-height:155%"><tbody><tr style="width:100%"><td style="padding:0">
    <img src="https://resend-attachments.s3.amazonaws.com/521fc63a-bd7c-4a5a-9c79-b3c095b60da5" style="display:block;outline:none;border:none;text-decoration:none;max-width:100%;border-radius:8px;height:auto" width="100%" />
    <h1 style="margin:0;padding:0.389em 0;font-size:2.25em;line-height:1.44em;font-weight:600">Bine ai venit, {name}!</h1>
    <p style="margin:0;padding:0.5em 0">Înscrierea <strong>{model_vehicle or "—"}</strong> a fost înregistrată cu succes.</p>
    <p style="margin:0;padding:0.5em 0">Email: {to}</p>
    <p style="margin:0;padding:0.5em 0">Nr. înmatriculare: {plate or "—"}</p>
    <p style="margin:0;padding:0.5em 0">VIN: {vin or "—"}</p>
    <p style="margin:0;padding:0.5em 0">NR. K: {k_code or "—"}</p>
    <br/>
    <p style="margin:0;padding:8px;text-align:center;font-size:1em">Dacă înregistrarea vehiculului tău nu a fost administrată de tine, contactează-ne pentru dezactivarea contului la <a href="mailto:support@mulberry.autos" style="color:#0670DB">support@mulberry.autos</a></p>
    <p style="margin:0;padding:0.5em 0;font-size:11px;text-align:center"><span style="color:#076f23">Recepționarea email-ului și continuarea utilizării <a href="https://mulberry.autos" style="color:#1e293b"><strong>mulberry.autos</strong></a> reprezintă acordul dumneavoastră la procesarea datelor de către platformă.</span></p>
    </td></tr></tbody></table></td></tr></tbody></table></body></html>"""
    _send(to, "Bun venit la Mulberry!", html)

def send_login_alert(to: str, name: str, ip: str = ""):
    rows = _rows(
        ("Cont", to, False),
        ("Data", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), False),
        ("IP", ip or "-", False),
    )
    html = _base(
        badge="AUTENTIFICARE",
        title="Autentificare reușită",
        subtitle="O nouă sesiune a fost deschisă pe contul tău Mulberry.",
        rows_html=rows,
        cta_label="Verifică contul →",
    )
    _send(to, "Autentificare Mulberry", html)

def send_pdf_downloaded(to: str, name: str, doc_name: str):
    rows = _rows(
        ("Document", doc_name, False),
        ("Cont", to, False),
        ("Data descărcării", datetime.now().strftime("%d.%m.%Y %H:%M"), False),
    )
    html = _base(
        badge="DOCUMENT",
        title="Document descărcat",
        subtitle="Un document a fost generat și descărcat din contul tău Mulberry.",
        rows_html=rows,
        cta_label="Vezi documentele mele →",
    )
    _send(to, "Document descărcat — Mulberry", html)


def send_booking_user(to: str, name: str, service: str, date: str, vin: str, plate: str, address: str = ""):
    rows = _rows(
        ("Serviciu", service, False),
        ("Data programării", date, True),
        ("Adresă service", address or "—", False),
        ("VIN", vin or "—", False),
        ("Nr. înmatriculare", plate or "—", False),
    )
    html = _base(
        badge="PROGRAMARE CONFIRMATĂ",
        title="Programarea ta a fost înregistrată",
        subtitle="Service-ul a primit detaliile vehiculului tău. Te așteptăm!",
        rows_html=rows,
        cta_label="Vezi programarea →",
    )
    _send(to, "Programare confirmată — Mulberry", html)


def send_booking_mechanic(mechanic_email: str, service: str, date: str, client_name: str,
                           client_email: str, vin: str, plate: str, make: str = "", model: str = "", year: str = ""):
    rows = _rows(
        ("Client", client_name, False),
        ("Email client", client_email, False),
        ("Serviciu solicitat", service, False),
        ("Data programării", date, True),
        ("Vehicul", f"{make} {model} {year}".strip(), False),
        ("VIN", vin or "—", False),
        ("Nr. înmatriculare", plate or "—", False),
    )
    html = _base(
        badge="PROGRAMARE NOUĂ",
        title="Ai o programare nouă",
        subtitle="Un client a rezervat un serviciu prin platforma Mulberry.",
        rows_html=rows,
        cta_label="Gestionează programările →",
        cta_url="https://mulberry.autos",
    )
    _send(mechanic_email, f"Programare nouă — {client_name} — Mulberry", html)
