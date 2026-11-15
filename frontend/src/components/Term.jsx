// Término técnico con su explicación en palabras simples. Se puede leer con el cursor (title)
// y con el teclado (tabIndex), y los lectores de pantalla leen la explicación completa.
export default function Term({ text, children }) {
  return (
    <abbr className="datil-term" title={text} tabIndex={0}>
      {children}
    </abbr>
  );
}
