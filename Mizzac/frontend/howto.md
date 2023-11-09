### How to install SPA for new Board

***

> ## Requirements
>
> *Node.js* : https://nodejs.org/en/download/
>
> if windows issue in VSC just restart
> 
 ```
 npm install -g @vue/cli
 ```

then in frontend/
```
vue create <boardname>
```

-> manual 

-> Babel, Router, Vuex, CSS Pre-processors, Linter / Formatter, Unit Testing, E2E Testing

-> Vue 3

-> Use history mode

-> Sass/SCSS

-> ESLint + Prettier

-> Lint on save

-> Jest

-> Cypress

-> In dedicated config files

In the board directory

```
npm install tailwindcss postcss autoprefixer
npx tailwindcss init -p
npm install daisyui

```

in tailwind.config.js

```
module.exports = {
  // ...
  plugins: [require('daisyui')],
}

```

in src/assets/css/main.css or src/index.css

```
@tailwind base;
@tailwind components;
@tailwind utilities;

```

in src/main.js

```
import './assets/css/main.css';

```

To start :

```
npm run serve
```
