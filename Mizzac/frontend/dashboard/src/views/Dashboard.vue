<template>
    <div>
      <h1 class="text-4xl font-bold text-center text-blue-500">Bienvenue sur le tableau de bord</h1>
      <!-- Ajoutez ici le contenu spécifique de votre HUB -->
      <!-- Exemple de lien de déconnexion, à adapter selon votre logique de routage -->
      <a href="#" @click="logout">Se déconnecter</a>
    </div>
  </template>
  
  <script>
  export default {
    name: 'dashboard',
    methods: {
      logout() {
        // Ajoutez ici votre logique de déconnexion
        // Par exemple, appeler une API de déconnexion et rediriger l'utilisateur
      }
    }
  }
  </script>
  

  