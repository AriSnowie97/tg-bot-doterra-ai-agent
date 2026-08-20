import "./App.css";
import styles from "./App.module.css";
import { Router } from "./Router";
import { Header } from "./components/Header";
import { Menu } from "./components/Menu";

function App() {

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