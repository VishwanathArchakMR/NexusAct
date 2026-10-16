import { AuthService } from "../services/auth";
import { Dashboard } from "./Dashboard";

export const App = () => {
  const auth = new AuthService();
  const dash = Dashboard();
  return {
    auth,
    dash,
  };
};
