import axios from "axios";

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:5000",
});

let onUnauthorized = () => {};
let onActivity = () => {};

export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler;
}

export function setActivityHandler(handler) {
  onActivity = handler;
}

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("datil_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Cualquier respuesta autenticada exitosa cuenta como actividad (refleja el
// touch_session del backend); un 401 fuerza cierre de sesion en el cliente.
apiClient.interceptors.response.use(
  (response) => {
    onActivity();
    return response;
  },
  (error) => {
    if (error.response?.status === 401) {
      onUnauthorized();
    }
    return Promise.reject(error);
  }
);

export default apiClient;
