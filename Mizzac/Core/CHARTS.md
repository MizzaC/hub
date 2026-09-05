# Graphiques partagés avec ApexCharts

## Intégration

Le layout `Core/templates/core/base.html` charge localement et une seule fois :

- `core/vendor/apexcharts/apexcharts.min.js` — ApexCharts 7.1.0 ;
- `core/js/charts.js` — façade commune Mizzac.

Toutes les applications qui héritent du layout partagé disposent donc de
`window.ApexCharts` et de `window.MizzacCharts`, sans CDN ni ajout de script
vendeur dans leurs templates.

La façade commune fournit :

- `MizzacCharts.mount(elementOuSelecteur, options)` ;
- `MizzacCharts.destroy(elementOuSelecteur)` et `destroyAll()` ;
- `MizzacCharts.palette` pour les couleurs communes ;
- `MizzacCharts.formatNumber(value, options)` avec la locale `fr-FR`.

Elle applique par défaut la police Tabler, la palette Mizzac, le fond
transparent, une légende basse, le thème clair/sombre actif et la préférence
système de réduction des animations. Tous les graphiques montés changent de
thème avec le bouton global.

## Exemple Django sûr

Les données serveur doivent passer par `json_script`, jamais par `safe` :

```django
<div id="exampleChart" role="img" aria-label="Évolution mensuelle"></div>
{{ chart_values|json_script:"example-chart-values" }}
<script>
  const values = JSON.parse(document.getElementById('example-chart-values').textContent);
  MizzacCharts.mount('#exampleChart', {
    chart: { type: 'line', height: 300 },
    series: [{ name: 'Valeur', data: values }],
    xaxis: { categories: ['Jan', 'Fév', 'Mar'] },
  });
</script>
```

Une description accessible doit rester associée au conteneur. Pour un
graphique essentiel, ajouter aussi un tableau ou résumé textuel afin que
l'information ne dépende pas uniquement du rendu visuel.

## Dépendance et licence

La version est verrouillée dans `package.json` et `package-lock.json`. Le build
copie le bundle et sa licence depuis `node_modules`, sans téléchargement côté
navigateur.

L'usage déclaré de Mizzac est strictement personnel, sans entreprise. Il relève
donc de la licence Community gratuite d'ApexCharts au moment de l'intégration.
Les fonctions premium ne sont pas utilisées. Si le projet devient commercial,
est redistribué ou permet à des tiers de configurer des graphiques interactifs,
la licence devra être réévaluée avant diffusion.
