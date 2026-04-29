# Render Deployment Setup Guide

This guide explains how to deploy your Herbal Clinic Backend on Render (free tier).

## Prerequisites
- GitHub repository with your code pushed
- Render account (free): https://render.com

## Step 1: Create a PostgreSQL Database on Render

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click **+ New** → **PostgreSQL**
3. Fill in the form:
   - **Name**: `herbal-clinic-db`
   - **Database**: `herbal_clinic`
   - **User**: `herbal_clinic_user`
   - **Region**: Choose closest to your location
   - **Plan**: Free (for development)
4. Click **Create Database**
5. Copy the **Internal Database URL** (you'll need this later)

## Step 2: Deploy the Web Service on Render

### Option A: Using render.yaml (Automated Blueprint)

1. Push the `render.yaml` file to your repository
2. Go to [Render Dashboard](https://dashboard.render.com/)
3. Click **+ New** → **Blueprint**
4. Connect your GitHub repository
5. Follow the prompts to set environment variables
6. Click **Deploy**

### Option B: Manual Setup

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click **+ New** → **Web Service**
3. Select your GitHub repository
4. Fill in the form:
   - **Name**: `herbal-clinic-backend`
   - **Environment**: Python
   - **Build Command**: `chmod +x build.sh && ./build.sh`
   - **Start Command**: `gunicorn backend.wsgi:application`
   - **Plan**: Free

5. Under **Environment Variables**, click **Add Environment Variable** and set:

## Step 3: Set Environment Variables on Render

On the Render Web Service dashboard, add the following environment variables:

### 1. **SECRET_KEY** (Required)
   - Generate a new Django secret key:
     ```bash
     python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
     ```
   - Copy the output and paste it in Render
   - **Example**: `dk(x6*=@#*$%^&*(1234567890abcdef1234567890ab`

### 2. **DEBUG**
   - **Value**: `False` (for production)

### 3. **ALLOWED_HOSTS** (Required)
   - **Value**: `your-service-name.onrender.com`
   - **Example**: If your Render service is `herbal-clinic-backend`, use: `herbal-clinic-backend.onrender.com`
   - For multiple hosts: `host1.com,host2.com,localhost`

### 4. **CORS_ALLOWED_ORIGINS** (Required)
   - **Value**: Frontend URL(s) that will access this API
   - **Example**: `https://your-frontend.vercel.app,https://your-frontend.netlify.app`
   - For local development: `http://localhost:3000,http://localhost:8000`

### 5. **DATABASE_URL** (Auto-set if linked)
   - If you linked a PostgreSQL database in Render, this is **automatically set**
   - If not, get it from the database connection string:
   - Format: `postgresql://user:password@host:port/database`
   - **Example**: `postgresql://herbal_clinic_user:password123@dpg-abc123.onrender.com:5432/herbal_clinic`

## Step 4: Verify Deployment

Once deployed:

1. Check logs in Render dashboard (should see migration and static file collection)
2. Visit `https://your-service-name.onrender.com/admin/` to verify it's running
3. Use credentials: **Username**: `admin`, **Password**: `admin123`
4. The admin user has `role='admin'` for frontend role detection

## Step 5: Connect Frontend

In your frontend `.env.production` or environment variables, set:

```env
REACT_APP_API_URL=https://your-service-name.onrender.com
```

Update your frontend to use `process.env.REACT_APP_API_URL` in API calls.

## Troubleshooting

### Build fails with "Module not found" errors
- Ensure `requirements.txt` has all dependencies
- Check `build.sh` has executable permissions (it's handled by the build command)

### Admin user not created
- Check Render logs for errors in the Python shell command
- Ensure the `accounts.User` model has a `role` field

### Static files not loading
- WhiteNoise is configured in settings
- If images/CSS don't load, run: `python manage.py collectstatic --noinput`

### Database connection fails
- Verify `DATABASE_URL` is correct in Render environment variables
- Ensure PostgreSQL database is online
- Check that migrations run successfully in logs

### CORS errors in frontend
- Update `CORS_ALLOWED_ORIGINS` with your frontend URL
- Remember to include `https://` prefix
- Render auto-assigns a URL like `your-service.onrender.com`

## Important Notes

⚠️ **Never commit `db.sqlite3` to production** — it's only for local development

⚠️ **Generate a strong SECRET_KEY** for production, don't use the default

⚠️ **Keep ALLOWED_HOSTS specific** — don't use `*` in production

✅ **Save your credentials securely** — admin username/password are set in `build.sh` and can be changed after first login

## Next Steps

1. Deploy frontend (React/Next.js) on Vercel or Netlify
2. Update frontend API URL to point to your Render backend
3. Test API endpoints with token authentication
4. Monitor logs for any issues

For more help: [Render Documentation](https://render.com/docs)
