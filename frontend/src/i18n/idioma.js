// Selector de idioma (español / inglés) de Datil. La página se arma en español y este módulo traduce el DOM con el diccionario de en.js:
// cada texto nuevo que React pinta (también los que llegan del servidor) pasa por aquí. Cambiar de idioma guarda la preferencia y recarga
// (la sesión sigue en localStorage), así las fechas y los montos también salen con el formato del idioma.
import { EXACTO, PLANTILLAS } from "./en.js";

const CLAVE = "idioma";

export function idiomaActual() {
  try {
    const q = new URLSearchParams(window.location.search).get("lang");
    if (q === "en" || q === "es") return q;
    return localStorage.getItem(CLAVE) === "en" ? "en" : "es";
  } catch {
    return "es";
  }
}

export const localeActual = () => (idiomaActual() === "en" ? "en-US" : "es-MX");

const NUM = String.raw`[-+]?\$?\d[\d.,]*%?`;
const escapar = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const COMPILADAS = PLANTILLAS.map(([es, en]) => {
  const fuente = es
    .split(/(\{n\}|\{\*\})/)
    .map((p) => (p === "{n}" ? `(${NUM})` : p === "{*}" ? "(.+?)" : escapar(p)))
    .join("");
  return [new RegExp(`^${fuente}$`), en];
});

const normal = (s) => s.replace(/\s+/g, " ").trim();

// Devuelve la traducción de un texto en español, o null si no hay.
export function traducir(es) {
  const t = normal(es);
  if (!t) return null;
  if (Object.hasOwn(EXACTO, t)) return EXACTO[t];
  for (const [re, en] of COMPILADAS) {
    const m = t.match(re);
    if (m) return en.replace(/\{(\d+)\}/g, (_, i) => m[i]);
  }
  return null;
}

const ATRIBUTOS = ["placeholder", "aria-label", "title", "alt"];

function traducirTexto(nodo) {
  const original = nodo.nodeValue;
  const en = traducir(original);
  if (en === null) return;
  const nuevo = original.match(/^\s*/)[0] + en + original.match(/\s*$/)[0];
  if (nuevo !== original) nodo.nodeValue = nuevo;  // sin esta guarda un texto igual en ambos idiomas se re-dispararía para siempre
}

function traducirAtributos(el) {
  for (const a of ATRIBUTOS) {
    const v = el.getAttribute?.(a);
    if (!v) continue;
    const en = traducir(v);
    if (en !== null && en !== v) el.setAttribute(a, en);
  }
}

function recorrer(raiz) {
  if (raiz.nodeType === Node.TEXT_NODE) {
    traducirTexto(raiz);
    return;
  }
  if (raiz.nodeType !== Node.ELEMENT_NODE || ["SCRIPT", "STYLE"].includes(raiz.tagName)) return;
  traducirAtributos(raiz);
  const arbol = document.createTreeWalker(raiz, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
  while (arbol.nextNode()) {
    const n = arbol.currentNode;
    if (n.nodeType === Node.TEXT_NODE) {
      if (!["SCRIPT", "STYLE"].includes(n.parentElement?.tagName)) traducirTexto(n);
    } else {
      traducirAtributos(n);
    }
  }
}

export function iniciarIdioma() {
  const en = idiomaActual() === "en";
  document.documentElement.lang = en ? "en" : "es";

  const boton = document.createElement("button");
  boton.type = "button";
  boton.className = "datil-idioma";
  boton.textContent = en ? "ES" : "EN";
  boton.setAttribute("aria-label", en ? "Cambiar a español" : "Switch to English");
  boton.lang = en ? "es" : "en";
  boton.addEventListener("click", () => {
    try {
      localStorage.setItem(CLAVE, en ? "es" : "en");
    } catch {
      // sin almacenamiento: se queda como está
    }
    const url = new URL(window.location.href);
    url.searchParams.delete("lang");  // ?lang= mandaría sobre lo que se acaba de elegir
    window.location.replace(url);
  });
  document.body.append(boton);

  if (!en) return;
  document.title = traducir(document.title) ?? document.title;
  recorrer(document.body);
  new MutationObserver((registros) => {
    for (const r of registros) {
      if (r.type === "characterData") traducirTexto(r.target);
      else if (r.type === "attributes") traducirAtributos(r.target);
      else r.addedNodes.forEach(recorrer);
    }
  }).observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATRIBUTOS });
}
