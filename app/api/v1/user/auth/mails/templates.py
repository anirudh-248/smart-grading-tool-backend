def sign_up_template(OTP)->str:
    return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SmartGrader - Account Verification</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 0;
            background-color: #f4f4f4;
        }
        .container {
            max-width: 600px;
            margin: 20px auto;
            padding: 20px;
            background-color: #ffffff;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }
        .logo {
            text-align: center;
        }
        .logo img {
            width: 100px;
        }
        .content {
            padding: 10px;
            text-align: center;
        }
        .otp-container {
            background: linear-gradient(135deg, #FFB800 0%, #FF8A00 100%);
            padding: 20px;
            border-radius: 8px;
            margin: 30px 0;
            text-align: center;
        }
        .otp {
            font-size: 32px;
            font-weight: bold;
            color: white;
            letter-spacing: 5px;
            margin: 10px 0;
        }
        .copy-button {
            background: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            font-weight: bold;
            color: #FF8A00;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .copy-button:hover {
            background: #f0f0f0;
        }
        .footer {
            text-align: center;
            color: #666;
            font-size: 12px;
            margin-top: 30px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">
            <img src="https://storage.googleapis.com/smart-grading-tool/sg-logo.png" alt="SmartGrader Logo">
        </div>
        <div class="content">
            <h2>Verify Your Account</h2>
            <p>Thank you for joining SmartGrader! Please use the following OTP to verify your account:</p>

            <div class="otp-container">
                <div class="otp">"""+OTP+"""</div>
            </div>

            <p>This OTP will expire in 10 minutes. If you didn't request this verification, please ignore this email.</p>
        </div>
        <div class="footer">
            <p>© 2025 SmartGrader. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""


def forgot_password_template(OTP)->str:
    return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SmartGrader - Account Verification</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 0;
            background-color: #f4f4f4;
        }
        .container {
            max-width: 600px;
            margin: 20px auto;
            padding: 20px;
            background-color: #ffffff;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }
        .logo {
            text-align: center;
        }
        .logo img {
            width: 100px;
        }
        .content {
            padding: 10px;
            text-align: center;
        }
        .otp-container {
            background: linear-gradient(135deg, #FFB800 0%, #FF8A00 100%);
            padding: 20px;
            border-radius: 8px;
            margin: 30px 0;
            text-align: center;
        }
        .otp {
            font-size: 32px;
            font-weight: bold;
            color: white;
            letter-spacing: 5px;
            margin: 10px 0;
        }
        .copy-button {
            background: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            font-weight: bold;
            color: #FF8A00;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .copy-button:hover {
            background: #f0f0f0;
        }
        .footer {
            text-align: center;
            color: #666;
            font-size: 12px;
            margin-top: 30px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">
            <img src="https://storage.googleapis.com/al-media-bucket/sg-logo.png" alt="SmartGrader Logo">
        </div>
        <div class="content">
            <h2>Verify Your Account</h2>
            <p>Forgot Password ? Please use the following OTP to verify your account:</p>

            <div class="otp-container">
                <div class="otp">"""+OTP+"""</div>
            </div>

            <p>This OTP will expire in 24 hours. If you didn't request this verification, please ignore this email.</p>
        </div>
        <div class="footer">
            <p>© 2025 SmartGrader. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""
