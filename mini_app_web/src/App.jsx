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
    // Якщо відкрили за конкретним посиланням (наприклад, стаття), не скидаємо на Головну.
    // Якщо хеш порожній або просто '#/', переходимо на Головну (щоб скинути кеш телеграму, якщо він відкриває стару сторінку).
    if (!window.location.hash || window.location.hash === '#/' || window.location.hash === '') {
      navigate("/");
    }
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