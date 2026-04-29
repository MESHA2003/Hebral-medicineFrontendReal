# Herbal Clinic Backend - Deployment Checklist

## ✅ Files Created/Updated

### 1. **backend/settings.py** (UPDATED)
- ✅ Environment variable configuration for `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`
- ✅ Database URL handling with `dj_database_url` (PostgreSQL on Render, SQLite fallback)
- ✅ WhiteNoise middleware for static file serving
- ✅ CORS configuration from `CORS_ALLOWED_ORIGINS` env var
- ✅ Production security settings (SSL, HSTS, CSP) when `DEBUG=False`
- ✅ Static file collection with compression via WhiteNoise
- ✅ All existing custom apps preserved (`accounts`, `clinic`)

### 2. **build.sh** (ALREADY UPDATED)
- ✅ Installs all dependencies from `requirements.txt`
- ✅ Runs database migrations
- ✅ Collects static files
- ✅ Creates admin superuser with `role='admin'` (required for frontend)
- ✅ Handles existing admin user by updating role

### 3. **render.yaml** (NEW)
- ✅ Render Blueprint for automatic infrastructure setup
- ✅ Configures Python 3.11 web service
- ✅ Sets up PostgreSQL database (free tier)
- ✅ Defines environment variables with prompts
- ✅ Uses `gunicorn` as production server

### 4. **RENDER_SETUP.md** (NEW)
- ✅ Step-by-step deployment guide
- ✅ Database creation instructions
- ✅ Environment variable setup (all 5 required vars explained)
- ✅ Troubleshooting guide
- ✅ Frontend integration instructions

### 5. **.env.example** (NEW)
- ✅ Template for local development environment variables
- ✅ Comments on production configurations

### 6. **requirements.txt** (ALREADY UPDATED)
```
Django==5.0.3
djangorestframework==3.14.0
django-cors-headers==4.3.1
djangorestframework-simplejwt==5.3.1
Pillow==10.2.0
psycopg2-binary==2.9.9
gunicorn==21.2.0
whitenoise==6.6.0
dj-database-url==2.1.0
```

---

## 🚀 Quick Deployment Steps

### Local Development (no changes needed)
```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```
- Uses SQLite by default
- Accepts all CORS origins (`http://localhost:3000`)

### Production on Render

1. **Push to GitHub**
   ```bash
   git add .
   git commit -m "Prepare for Render deployment"
   git push
   ```

2. **Create PostgreSQL Database**
   - Visit Render Dashboard → New → PostgreSQL
   - Copy the Internal Database URL

3. **Deploy Web Service**
   - Option A: Upload `render.yaml` → Render Dashboard → New → Blueprint
   - Option B: Manual setup as described in RENDER_SETUP.md

4. **Set Environment Variables** (in Render dashboard)
   | Variable | Value |
   |----------|-------|
   | `SECRET_KEY` | Generate: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
   | `DEBUG` | `False` |
   | `ALLOWED_HOSTS` | `your-service-name.onrender.com` |
   | `CORS_ALLOWED_ORIGINS` | `https://your-frontend-url.com` |
   | `DATABASE_URL` | Auto-set by Render if linked; or provide PostgreSQL URL |

5. **Deploy** → Render runs `build.sh` automatically

---

## 📋 Key Features

### Security (Production)
- HTTPS redirect (`SECURE_SSL_REDIRECT`)
- HSTS headers (1 year, includes subdomains)
- Secure cookies (SSL-only)
- CSRF protection
- XFrame options (DENY)
- Content Security Policy

### Performance
- WhiteNoise for efficient static file serving
- Gzip compression
- Database connection pooling (`conn_max_age=600`)

### Admin User
- **Username**: `admin`
- **Password**: `admin123`
- **Role**: `admin` (for frontend detection)
- Auto-created on first deployment

### Static Files
- Collected in `staticfiles/` directory
- Served by WhiteNoise (no separate web server needed)
- CSS, JS, images all served efficiently

---

## 🔗 Environment Variables Explained

| Variable | Purpose | Local Default | Production |
|----------|---------|----------------|-----------|
| `SECRET_KEY` | Django security key | Unsafe default (dev) | Must generate |
| `DEBUG` | Debug mode | `True` | `False` |
| `ALLOWED_HOSTS` | Allowed hostnames | `localhost,127.0.0.1` | Your Render URL |
| `CORS_ALLOWED_ORIGINS` | Frontend CORS policy | `http://localhost:3000,...` | Your frontend URL |
| `DATABASE_URL` | Database connection | (empty, uses SQLite) | PostgreSQL URL |

---

## 📚 Documentation Files

- **RENDER_SETUP.md** - Complete deployment guide with step-by-step instructions
- **.env.example** - Template for environment configuration
- **build.sh** - Automated build script for production

---

## ⚠️ Important Reminders

1. **Generate a strong SECRET_KEY** for production
2. **Never commit sensitive data** (use environment variables)
3. **Update ALLOWED_HOSTS** with your actual Render domain
4. **Set CORS_ALLOWED_ORIGINS** to your frontend URL (not `*`)
5. **Change admin password** after first login
6. **Monitor Render logs** during first deployment
7. **Test API endpoints** from your frontend before going live

---

## ✅ Pre-Deployment Checklist

- [ ] All files created/updated as listed above
- [ ] `requirements.txt` includes all 9 dependencies
- [ ] `build.sh` is executable (or use `chmod +x build.sh`)
- [ ] Code pushed to GitHub
- [ ] `accounts.User` model has `role` field
- [ ] Frontend API URL will point to Render service
- [ ] Environment variables prepared (SECRET_KEY, etc.)
- [ ] PostgreSQL database created on Render
- [ ] Admin credentials documented securely

---

## 🆘 Support

For issues or questions:
- Check **RENDER_SETUP.md** Troubleshooting section
- Review Render logs: Dashboard → Web Service → Logs
- Verify environment variables are set correctly
- Ensure database is online and accessible
- Test migrations locally before deploying

---

**Last Updated**: April 29, 2026
**Django Version**: 5.0.3
**Target Platform**: Render (Free Tier)
