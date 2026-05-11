import base64
import os

os.chdir('herbal-clinic-frontend')
with open('src/assets/Logo.jpg', 'rb') as f:
    img_data = f.read()
b64 = base64.b64encode(img_data).decode()
js_content = 'const LOGO_BASE64 = "' + 'data:image/jpeg;base64,' + b64 + '";\nexport default LOGO_BASE64;\n'
with open('src/utils/logoBase64.js', 'w') as f:
    f.write(js_content)
print('Done: ' + str(len(b64)) + ' chars')