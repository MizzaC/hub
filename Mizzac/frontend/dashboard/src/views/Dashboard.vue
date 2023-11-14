<template>
    <div>
      <h1>Bienvenue sur le DashBoard</h1>
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
  
  <style>
  /* Vos styles CSS spécifiques à Hub.vue ici */
  </style>
  