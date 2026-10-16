import { App } from "./components/App";
import { AuthService } from "./services/auth";

export function initializeApp() {
  const auth = new AuthService();
  const app = App();
  return { auth, app };
}
