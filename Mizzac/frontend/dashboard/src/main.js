import Vue from "vue";
import dashboard from "./views/Dashboard.vue";

new Vue({
  render: (h) => h(dashboard),
}).$mount("#dashboard");
