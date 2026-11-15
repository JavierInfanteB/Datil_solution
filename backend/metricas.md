# Métricas de Datil Solutions (bonos y acciones)

Datil solo mide riesgo: cuánto y qué tan feo puede caer algo. Nunca calcula ganancias esperadas, no predice si
un instrumento va a subir o bajar, y no es asesoría financiera. El pasado no garantiza el futuro.

## Acciones: puntaje de riesgo

Pregunta que responde: "si compro esto y lo mantengo un año, ¿qué tan probable es que sea una mala experiencia?".
El puntaje va de 0 a 100 y es el promedio ponderado de cuatro señales históricas:

- Volatilidad anual (3 años), peso 25: qué tanto sube y baja el precio día a día. Más volatilidad significa más sorpresas, buenas y malas.
- Pérdida en los peores días (3 años), peso 20: la pérdida diaria promedio en el 5% de los peores días.
- Caída máxima (3 años), peso 15: la mayor caída que ha tenido el precio desde un punto alto hasta uno bajo.
- Beta contra el mercado global, peso 40: qué tanto se mueve la acción comparada con el mercado. Mayor a 1: se mueve más que el mercado; menor a 1: se mueve menos.

Niveles: puntaje menor a 30 es riesgo bajo; de 30 a menos de 55 es riesgo medio; 55 o más es riesgo alto.
Si a una acción le falta historia para la beta, esa señal se excluye y las demás se reescalan. Con menos de
un año de historia no se calcula el riesgo.

Volatilidad, pérdidas y caídas se miden en pesos, porque es el dinero del usuario: una acción extranjera también
lleva el riesgo del tipo de cambio. La beta se mide en la moneda original de la acción, con rendimientos semanales.

En pruebas con 10 años de historia, las acciones de riesgo alto tuvieron caídas de 30% o más en el año siguiente
casi 3 veces más seguido (60% contra 21%) que las de riesgo bajo.

## Acciones: otros datos en pantalla

- Costo promedio: lo que se pagó en promedio por cada título.
- Valor hoy y ganancia: valuación con el último precio, en pesos. Las acciones extranjeras se convierten con el tipo de cambio del día.
- Comparador de acciones: muestra varias acciones en pesos con base 100 en el último año, para ver cuál se movió más.
- pp (puntos porcentuales): la diferencia entre dos tasas. Si una tasa pasa de 10% a 10.5%, subió 0.5 pp.

## Bonos gubernamentales

Instrumentos: CETES (28, 91, 182, 364 y 728 días), Bonos M de tasa fija (3, 5, 10, 20 y 30 años), Udibonos de
tasa real (3, 10, 20 y 30 años) y BPA (BPAG28 mensual, BPAG91 trimestral y BPA182 semestral con protección a la inflación).

- Tasa: en bonos, lo que la plataforma muestra como "precio" es la tasa vigente en porcentaje, y sus cambios se miden en puntos porcentuales (pp).
- CETES: se compran con descuento (por debajo de su valor nominal de 10 pesos) y al vencer pagan el nominal. No pagan cupones.
- Bono M: se compra cerca de su valor nominal y paga cupones de tasa fija; al vencer paga el nominal más sus cupones.
- Udibonos: pagan una tasa real sobre un valor que se ajusta con la inflación.
- Tasa contratada: la tasa de la subasta en la que entró la compra.
- Valor hoy: lo que se recibiría al vender hoy, a las tasas de mercado de hoy. Si no hay tasas de mercado disponibles se muestra el valor devengado.
- Si lo mantienes: el valor al vencimiento si no se vende antes.
- Próximo cupón: fecha y monto del siguiente pago de cupón.

Subastas: Banxico subasta los martes y liquida el jueves. Una orden entra a la subasta del próximo martes si se
registra a más tardar el lunes, y se puede cancelar hasta ese día. No todos los instrumentos se subastan cada semana.

Vender antes del vencimiento: se puede vender a precio de mercado hasta 3 días hábiles antes del vencimiento. Si
las tasas subieron desde la compra se recibe menos, y si bajaron, más. Si se mantiene hasta el final se recibe lo pactado.

## Riesgo del portafolio

- Puntaje ponderado: el puntaje de riesgo de las acciones, pesado por lo que representa cada una en la cartera.
- Concentración: qué parte de la cartera está en efectivo y en cada moneda.
- Comportamiento histórico: caída máxima, volatilidad y pérdida en los peores días de la cartera completa, con los pesos de hoy.
- Escenarios: cuánto cambiaría el valor de la cartera si las acciones caen 20%, si el peso se aprecia 10% (valen menos los activos en moneda extranjera) y si las tasas de interés suben 1 punto (solo cuenta si se venden los bonos antes de que venzan).
