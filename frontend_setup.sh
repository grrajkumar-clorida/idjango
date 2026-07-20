#!/bin/bash
# Frontend Setup Script for React + Tailwind CSS

echo "🚀 Setting up React + Tailwind CSS Frontend..."

# Navigate to project root
cd /home/gr8/snap/Django/idjango

# Check if frontend directory exists
if [ -d "frontend" ]; then
    echo "⚠️  Frontend directory already exists. Skipping creation."
else
    echo "📦 Creating React app with Vite..."
    npm create vite@latest frontend -- --template react
fi

# Navigate to frontend directory
cd frontend

echo "📥 Installing dependencies..."
npm install

echo "📥 Installing additional packages..."
npm install axios react-router-dom @tanstack/react-query recharts react-hook-form zustand

echo "📥 Installing Tailwind CSS..."
npm install -D tailwindcss postcss autoprefixer

echo "⚙️  Initializing Tailwind CSS..."
npx tailwindcss init -p

echo "✅ Frontend setup complete!"
echo ""
echo "Next steps:"
echo "1. cd frontend"
echo "2. npm run dev"
echo "3. Configure Tailwind CSS (see FRONTEND_SETUP.md)"
echo "4. Start building components!"
