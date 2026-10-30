import { mount } from "svelte";
import "./app.css";
import App from "./App.svelte";
import Burbuja from "./componentes/Burbuja.svelte";

// La burbuja flotante del escritorio es otra ventana con esta misma página (index.html?burbuja): solo dibuja la burbuja
const esBurbuja = new URLSearchParams(location.search).has("burbuja");
export default mount(esBurbuja ? Burbuja : App, { target: document.getElementById("app") });
