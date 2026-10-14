import React from "react";
import { Header } from "../components/Header";
import { Footer } from "../components/Footer";
import { SystemStatusDashboard } from "../features/system-status/SystemStatusDashboard";
import "./App.css";

export const App: React.FC = () => {
  return (
    <div className="app-layout">
      <Header />
      <div className="app-content">
        <SystemStatusDashboard />
      </div>
      <Footer />
    </div>
  );
};

export default App;
