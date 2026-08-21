import "./App.css";
import styles from "./App.module.css";
import { Router } from "./Router";
import { Header } from "./components/Header";
import { Menu } from "./components/Menu";
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

function App() {
  const navigate = useNavigate();

  useEffect(() => {
    // При кожному новому запуску (mount) примусово відкриваємо Головну
    navigate("/");
  }, []);

  return (
    <>
      <div className={styles.wrapAll}>
        <Header />
        <div className={styles.appWrapper}>
          <Router />
        </div>
          <Menu />
      </div>
    </>
  );
}

export default App;