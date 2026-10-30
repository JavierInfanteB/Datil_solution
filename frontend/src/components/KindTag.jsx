import { KIND_LABEL } from "../utils/avisos";

// El riesgo y la acción sugerida usan los colores de los niveles de riesgo; el aviso general, uno neutro.
const KIND_CLASS = { riesgo: "datil-risk datil-risk-alto", accion: "datil-risk datil-risk-medio", aviso: "datil-chip" };

export default function KindTag({ kind }) {
  return <span className={KIND_CLASS[kind]}>{KIND_LABEL[kind]}</span>;
}
