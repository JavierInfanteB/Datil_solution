// Qué pasa con el dinero de un bono o CETES al vencer (mismos ids que REINVEST_MODES en backend/utils/bond_engine.py).
// Como la reinversión automática de cetesdirecto, va a CETES a 28 días.
export const REINVEST_LABEL = {
  none: "No reinvertir (queda en efectivo)",
  all: "Reinvertir todo en CETES a 28 días",
  same: "Reinvertir solo el capital en CETES a 28 días (la ganancia queda en efectivo)",
};
