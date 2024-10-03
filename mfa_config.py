import os
import base64
import pyotp
import qrcode

SECRET_FILE = 'mfa_secret.key'
MFA_SETUP_FILE = 'mfa_setup.txt'

def get_or_create_secret():
    if os.path.exists(SECRET_FILE):
        with open(SECRET_FILE, 'r') as f:
            return f.read().strip()
    else:
        secret = base64.b32encode(os.urandom(10)).decode('utf-8')
        with open(SECRET_FILE, 'w') as f:
            f.write(secret)
        return secret

MFA_SECRET = get_or_create_secret()

def is_mfa_setup_complete():
    return os.path.exists(MFA_SETUP_FILE)

def mark_mfa_setup_complete():
    with open(MFA_SETUP_FILE, 'w') as f:
        f.write('MFA setup completed')

def generate_qr_code():
    totp = pyotp.TOTP(MFA_SECRET)
    uri = totp.provisioning_uri("UserActivityMonitor", issuer_name="YourCompany")
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save("mfa_qr.png")
    print("QR code for MFA setup has been saved as 'mfa_qr.png'")
    print(f"If you can't scan the QR code, use this secret key manually: {MFA_SECRET}")

def verify_totp(token):
    totp = pyotp.TOTP(MFA_SECRET)
    return totp.verify(token)