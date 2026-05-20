# AgroVision Olive AI - GitHub et mise en ligne

## 1. Preparation Git locale

Le dossier n'etait pas encore initialise comme depot Git. Depuis la racine du projet :

```powershell
cd C:\Users\Win11\Downloads\pfe\agrovision-ai
git init -b main
git add .
git commit -m "Initial commit - AgroVision Olive AI"
```

Si Git demande votre identite :

```powershell
git config --global user.name "Iyed Ben Mohamed"
git config --global user.email "votre-email@example.com"
```

## 2. Push vers GitHub

Créez d'abord un depot vide sur GitHub, par exemple `agrovision-olive-ai`.

Puis utilisez :

```powershell
cd C:\Users\Win11\Downloads\pfe\agrovision-ai
git remote add origin https://github.com/VOTRE-USERNAME/agrovision-olive-ai.git
git push -u origin main
```

## 3. Frontend sur Vercel

Deployez uniquement le dossier `frontend`.

Reglages conseilles dans Vercel :

- Framework preset : `Vite`
- Root directory : `frontend`
- Build command : `npm run build`
- Output directory : `dist`

Variable d'environnement a ajouter dans Vercel :

```text
VITE_API_BASE=https://votre-backend.onrender.com
```

Le fichier `frontend/vercel.json` gere la redirection SPA vers `index.html`.

## 4. Backend sur Render

Le fichier `render.yaml` est deja pret.

Option simple :

1. Pousser le projet sur GitHub.
2. Dans Render, choisir `New +` puis `Web Service`.
3. Connecter le depot GitHub.
4. Selectionner le service detecte depuis `render.yaml`.

Variables a definir dans Render :

```text
ALLOWED_ORIGINS=https://votre-frontend.vercel.app
OPENWEATHER_API_KEY=votre-cle-si-vous-l-utilisez
OLLAMA_URL=
OLLAMA_MODEL=
```

Note pratique :

- si vous ne deployeez pas Ollama, l'assistant doit rester en mode fallback ;
- les modeles runtime utiles sont conserves dans le depot ;
- les gros datasets d'entrainement et les environnements locaux sont ignores.

## 5. Ordre recommande

1. Pousser le projet sur GitHub.
2. Deployer le backend sur Render.
3. Recuperer l'URL publique du backend.
4. Ajouter cette URL dans `VITE_API_BASE` sur Vercel.
5. Deployer le frontend.

## 6. Verification finale

- Frontend : `https://votre-projet.vercel.app`
- Backend : `https://votre-backend.onrender.com/health`

Le test backend doit renvoyer :

```json
{"status":"ok"}
```
