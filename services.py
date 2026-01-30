import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import config
from datetime import datetime, date, timedelta
import os

def send_email(subject, body, to_email, attachment_path=None):
    """Genel e-posta gönderme fonksiyonu"""
    from models import Company
    company = Company.query.first()
    db_settings = company.get_settings() if company else {}
    
    # DB ayarlarını öncelikli kullan, yoksa config kullan
    mail_server = db_settings.get('smtp_server') or config.MAIL_SERVER
    mail_port = int(db_settings.get('smtp_port') or config.MAIL_PORT)
    mail_user = db_settings.get('smtp_user') or config.MAIL_USERNAME
    mail_password = db_settings.get('smtp_password') or config.MAIL_PASSWORD
    mail_tls = db_settings.get('smtp_tls', config.MAIL_USE_TLS)
    mail_from_name = db_settings.get('smtp_from_name') or (company.SirketAdi if company else "ERP Sistemi")
    mail_sender = mail_user # Gönderen e-postası kullanıcı adı ile aynı olmalı genelde

    if not mail_user or not mail_password:
        return False, "E-posta ayarları yapılandırılmamış."

    try:
        msg = MIMEMultipart()
        msg['From'] = f"{mail_from_name} <{mail_sender}>" if mail_from_name else mail_sender
        msg['To'] = to_email
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'html', 'utf-8'))

        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(attachment_path))
            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment_path)}"'
            msg.attach(part)

        server = smtplib.SMTP(mail_server, mail_port)
        if mail_tls:
            server.starttls()
        server.login(mail_user, mail_password)
        server.send_message(msg)
        server.quit()
        return True, "E-posta başarıyla gönderildi."
    except Exception as e:
        return False, str(e)

def check_upcoming_vades(app):
    """Vadesi gelen çek ve borçları kontrol eder ve Windows bildirimi gönderir"""
    try:
        from plyer import notification
    except ImportError:
        return # plyer yüklü değilse bildirim gönderme

    from models import db, Finance, Debt
    with app.app_context():
        today = date.today()
        three_days_later = today + timedelta(days=3)

        # Çekler (Finans modelinde Kategori='Çek' olanlar)
        # Not: Çek vadesi genelde Aciklama içinde veya Finance.Tarih olarak tutuluyor olabilir.
        # Kullanıcının modelinde özel bir VadeTarihi yoksa Tarih alanını baz alabiliriz.
        checks = Finance.query.filter(
            Finance.Kategori.ilike('%çek%'),
            Finance.Tarih >= today,
            Finance.Tarih <= three_days_later
        ).all()

        for c in checks:
            notification.notify(
                title="Çek Vadesi Hatırlatıcı",
                message=f"{c.Tarih} tarihli {c.Tutar} TL tutarındaki çekin vadesi yaklaşıyor.",
                app_name="ERP Sistemi",
                timeout=10
            )

        # Borçlar
        debts = Debt.query.filter(
            Debt.VadeTarihi >= today,
            Debt.VadeTarihi <= three_days_later,
            Debt.Durum != 'Ödendi'
        ).all()

        for d in debts:
            notification.notify(
                title="Borç Ödeme Hatırlatıcı",
                message=f"{d.VadeTarihi} vadeli {d.BorcVeren} borcu yaklaşıyor. Tutar: {d.KalanTutar} TL",
                app_name="ERP Sistemi",
                timeout=10
            )

def send_daily_summary(app):
    """Günlük kasa özetini e-posta ile gönderir"""
    from models import db, Finance, Company
    with app.app_context():
        today = date.today()
        # Bugünün işlemlerini çek
        entries = Finance.query.filter(Finance.Tarih == today).all()
        
        income = sum(e.Tutar for e in entries if e.IslemTuru == 'Gelir')
        expense = sum(e.Tutar for e in entries if e.IslemTuru == 'Gider')
        
        company = Company.query.first()
        company_name = company.SirketAdi if company else "ERP Sistemi"
        
        # Alıcı e-postası (Ayarlardan veya varsayılan)
        # Şimdilik config.MAIL_DEFAULT_SENDER'a gönderelim
        recipient = config.MAIL_DEFAULT_SENDER
        if not recipient: return

        subject = f"Günlük Kasa Özeti - {today.strftime('%d.%m.%Y')}"
        
        html_body = f"""
        <html>
            <body style="font-family: sans-serif;">
                <h2 style="color: #4848e5;">{company_name} - Günlük Özet</h2>
                <p><b>Tarih:</b> {today.strftime('%d.%m.%Y')}</p>
                <hr>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr style="background-color: #f6f6f8;">
                        <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">Toplam Gelir</th>
                        <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">Toplam Gider</th>
                        <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">Net Durum</th>
                    </tr>
                    <tr>
                        <td style="padding: 10px; color: green; font-weight: bold;">{income:.2f} TL</td>
                        <td style="padding: 10px; color: red; font-weight: bold;">{expense:.2f} TL</td>
                        <td style="padding: 10px; font-weight: bold;">{income - expense:.2f} TL</td>
                    </tr>
                </table>
                <br>
                <h3>İşlem Detayları:</h3>
                <ul style="list-style: none; padding: 0;">
                    {"".join([f'<li style="padding: 8px; border-bottom: 1px solid #eee;"><b>{e.IslemTuru}:</b> {e.Kategori} - {e.Tutar:.2f} TL ({e.Aciklama or ""})</li>' for e in entries])}
                </ul>
                <p style="font-size: 12px; color: #888; margin-top: 20px;">Bu rapor otomatik olarak gönderilmiştir.</p>
            </body>
        </html>
        """
        
        send_email(subject, html_body, recipient)

def get_net_hours(config):
    """Calculates net working hours from a day config."""
    if not config or not config.get('active'): return 0.0
    s = config.get('start', '08:30')
    e = config.get('end', '18:00')
    b = float(config.get('break') if config.get('break') is not None else 90)
    try:
        sh, sm = map(int, s.split(':'))
        eh, em = map(int, e.split(':'))
        diff = (eh * 60 + em) - (sh * 60 + sm)
        return max(0, (diff - b) / 60.0)
    except: return 0.0

def resolve_multiplier(saved_carpan, setting_mult):
    """
    Decides whether to use the saved multiplier or the one from settings.
    If the saved multiplier is one of the old hardcoded defaults (1.5 or 2.0)
    and differs from the current setting, we prefer the current setting to 
    ensure consistency across the system.
    """
    if saved_carpan is None:
        return setting_mult
    # 1.5 and 2.0 are common. We also include 2.5 and 3.0 as they are common weekend configurations.
    # If the saved value is one of these "standard" values but currently differs from the setting,
    # we assume it was an old default and update it to the new company setting.
    standard_multipliers = [1.0, 1.25, 1.5, 2.0, 2.5, 3.0]
    if saved_carpan in standard_multipliers and saved_carpan != setting_mult:
        return setting_mult
    return float(saved_carpan)

def get_payroll_for_person(p, today, weekly_schedule, public_holidays, monthly_hours, daily_net_work_hours, person_deductions):
    """Calculates payroll data for a person in a given month."""
    from models import Puantaj
    first_day = date(today.year, today.month, 1)
    if today.month == 12:
        next_month_first = date(today.year + 1, 1, 1)
    else:
        next_month_first = date(today.year, today.month + 1, 1)
    
    m_hours = float(monthly_hours or 225.0)
    if m_hours <= 0: m_hours = 225.0
    
    # Calculate person-specific hourly rate (Legal standard: 225h/month)
    salary = float(p.NetMaas or 0)
    person_hourly_rate = salary / m_hours

    # Detailed overtime and absence calculation (within the selected month)
    puantaj_records = Puantaj.query.filter(
        Puantaj.PersonelID == p.PersonelID,
        Puantaj.Tarih >= first_day,
        Puantaj.Tarih < next_month_first
    ).all()

    total_mesai_pay = 0.0
    total_absence_deduction_maas = 0.0
    total_absence_deduction_hours = 0.0
    total_overtime_hours = 0.0
    total_missing_hours = 0.0

    # Separate overtime by type for priority deduction
    overtime_by_type = {
        'public_holiday': {'hours': 0.0, 'pay': 0.0, 'multiplier': 2.0},
        'weekend': {'hours': 0.0, 'pay': 0.0, 'multiplier': 2.0},
        'weekday': {'hours': 0.0, 'pay': 0.0, 'multiplier': 1.5}
    }

    for pr in puantaj_records:
        days_map = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        day_name = days_map[pr.Tarih.weekday()]
        day_config = weekly_schedule.get(day_name, {})
        is_public_holiday = any(holiday['date'] == pr.Tarih.strftime('%Y-%m-%d') for holiday in public_holidays)
        
        # Get actual scheduled hours for this day
        scheduled_net_hours = get_net_hours(day_config)
        
        # 1. Determine the expected multiplier from settings
        if is_public_holiday:
            ot_type = 'public_holiday'
            setting_mult = float(next((h['multiplier'] for h in public_holidays if h['date'] == pr.Tarih.strftime('%Y-%m-%d')), 2.0))
        else:
            ot_type = 'weekend' if day_name in ['saturday', 'sunday'] else 'weekday'
            d_mult = 2.0 if ot_type == 'weekend' else 1.5
            setting_mult = float(day_config.get('multiplier', d_mult))

        # 2. Resolve final multiplier (using saved or setting)
        multiplier = resolve_multiplier(pr.Carpan, setting_mult)

        # 3. Calculate Overtime if any
        if pr.MesaiSaati > 0:
            pay = pr.MesaiSaati * person_hourly_rate * multiplier
            
            overtime_by_type[ot_type]['hours'] += pr.MesaiSaati
            overtime_by_type[ot_type]['pay'] += pay
            overtime_by_type[ot_type]['multiplier'] = multiplier
            
            total_mesai_pay += pay
            total_overtime_hours += pr.MesaiSaati

        # 4. Handle Absences / Missing Hours
        if (pr.Durum or '').lower() == 'gelmedi':
            total_missing_hours += scheduled_net_hours
            if pr.KesintiTuru == 'Mesai':
                total_absence_deduction_hours += scheduled_net_hours
            else:
                total_absence_deduction_maas += scheduled_net_hours * person_hourly_rate
        
        elif (pr.Durum or '').lower() == 'geç geldi' or (pr.EksikSaat and pr.EksikSaat > 0):
            missing = pr.EksikSaat or 0.0
            total_missing_hours += missing
            if pr.KesintiTuru == 'Mesai':
                total_absence_deduction_hours += missing
            else:
                total_absence_deduction_maas += missing * person_hourly_rate
        
        elif pr.MesaiSaati < 0:
            total_absence_deduction_hours += abs(pr.MesaiSaati)

    # 3. Apply Hour-based deductions from Overtime with Priority
    remaining_hours_to_deduct = total_absence_deduction_hours
    for ot_type in ['public_holiday', 'weekend', 'weekday']:
        if remaining_hours_to_deduct <= 0:
            break
        available_hours = overtime_by_type[ot_type]['hours']
        if available_hours > 0:
            deduct_hours = min(remaining_hours_to_deduct, available_hours)
            deduct_pay = (deduct_hours / available_hours) * overtime_by_type[ot_type]['pay']
            total_mesai_pay -= deduct_pay
            remaining_hours_to_deduct -= deduct_hours

    # 4. If still remaining hours, deduct from salary
    if remaining_hours_to_deduct > 0:
        total_absence_deduction_maas += remaining_hours_to_deduct * person_hourly_rate

    finance_deductions = person_deductions.get(p.PersonelID, 0.0)
    total_deductions = finance_deductions + total_absence_deduction_maas
    gross_pay = salary + max(0, total_mesai_pay)
    payroll = gross_pay - total_deductions

    return {
        'personel_id': p.PersonelID,
        'name': f"{p.Ad} {p.Soyad}",
        'net_salary': salary,
        'overtime_hours': total_overtime_hours,
        'total_work_hours': m_hours - total_missing_hours + total_overtime_hours,
        'overtime_pay': max(0, total_mesai_pay),
        'overtime_rate': person_hourly_rate,
        'missing_hours': total_missing_hours,
        'department': p.Departman,
        'deductions': total_deductions,
        'finance_deductions': finance_deductions,
        'absence_deductions': total_absence_deduction_maas,
        'payroll': payroll,
        'phone': p.Telefon,
        'email': p.Email
    }
