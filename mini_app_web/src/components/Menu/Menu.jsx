import { NavLink } from "react-router-dom";

import styles from "./Menu.module.css";
import heroImg from "/src/assets/hero.png";

const Menu = () => {

    const navigation = [
        ["/", "home", "Головна"],
        ["/chat", "chat", "Чат"],
        ["/articles", "articles", "Статті"],
        ["/contacts", "contacts", "Контакти"]
    ]

    return (
        <>
            <menu>
                <nav className={styles.navigation}>
                    {navigation.map(([src, alt, name], index) => (
                        <NavLink
                        to={src}
                        key={index + 1}
                        className={({isActive}) => isActive ? styles.active : ""}>
                            <img src={`${alt}.png`} alt={alt}/>
                            <h3>{name}</h3>
                        </NavLink>
                    ))}
                </nav>
            </menu>
        </>
    );
}

export {Menu};