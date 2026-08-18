import { NavLink } from "react-router-dom";

import styles from "./Menu.module.css";
import { HomeSvg, ChatSvg, ArticlesSvg, ContactsSvg } from "../../assets/images";

const Menu = () => {

    const navigation = [
        ["/", HomeSvg,"home", "Головна"],
        ["/chat", ChatSvg, "chat", "Чат"],
        ["/articles", ArticlesSvg, "articles", "Статті"],
        ["/contacts", ContactsSvg, "contacts", "Контакти"]
    ]

    return (
        <>
            <menu>
                <nav className={styles.navigation}>
                    {navigation.map(([to, Svg, alt, name], index) => (
                        <NavLink
                        to={to}
                        key={index + 1}
                        className={({isActive}) => isActive ? styles.active : ""}>
                            {
                            Svg
                            ? <Svg className={styles.Svg} />
                            : <p>{alt}</p>
                            }
                            <h3>{name}</h3>
                        </NavLink>
                    ))}
                </nav>
            </menu>
        </>
    );
}

export {Menu};