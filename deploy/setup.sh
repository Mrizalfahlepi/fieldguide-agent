#!/bin/bash
set -e

PROJECT_ID="fieldguide-agent"
REGION="asia-southeast1"

echo "FieldGuide GCP Setup"
echo "========================"

echo "1. Setting project..."
gcloud config set project $PROJECT_ID

echo "2. Enabling APIs..."
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com firestore.googleapis.com aiplatform.googleapis.com

echo "3. Creating Firestore database..."
gcloud firestore databases create --location=$REGION --type=firestore-native 2>/dev/null || echo "(Firestore exists, skipping)"

echo "4. Building backend..."
cd ../backend
gcloud builds submit --tag gcr.io/$PROJECT_ID/fieldguide-backend

echo "5. Deploying backend to Cloud Run..."
gcloud run deploy fieldguide-backend \
  --image gcr.io/$PROJECT_ID/fieldguide-backend \
  --platform managed --region $REGION \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=$GEMINI_API_KEY,GOOGLE_CLOUD_PROJECT=$PROJECT_ID \
  --memory 1Gi --timeout 300 --min-instances 0 --max-instances 3

BACKEND_URL=$(gcloud run services describe fieldguide-backend --region $REGION --format 'value(status.url)')
echo "Backend URL: $BACKEND_URL"

echo "6. Building frontend..."
cd ../frontend
BACKEND_WS=$(echo $BACKEND_URL | sed 's/https/wss/')
echo "VITE_BACKEND_URL=$BACKEND_WS" > .env.production
gcloud builds submit --tag gcr.io/$PROJECT_ID/fieldguide-frontend

echo "7. Deploying frontend..."
gcloud run deploy fieldguide-frontend \
  --image gcr.io/$PROJECT_ID/fieldguide-frontend \
  --platform managed --region $REGION \
  --allow-unauthenticated --memory 256Mi

FRONTEND_URL=$(gcloud run services describe fieldguide-frontend --region $REGION --format 'value(status.url)')

echo ""
echo "DEPLOYMENT COMPLETE!"
echo "========================"
echo "Backend:  $BACKEND_URL"
echo "Frontend: $FRONTEND_URL"
echo "Open $FRONTEND_URL on your phone!"
