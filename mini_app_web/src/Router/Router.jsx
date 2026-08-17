import { Routes, Route } from "react-router-dom";

import { Home } from "../components/pages/Home";
import { Chat } from "../components/pages/Chat";
import { Articles } from "../components/pages/Articles";
import { Contacts } from "../components/pages/Contacts";
import { NotFound } from "../components/pages/NotFound";


const Router = () => {
    return (
        <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/articles" element={<Articles />} />
            <Route path="/contacts" element={<Contacts />} />

            <Route path="*" element={<NotFound />} />
        </Routes>
    );
}

export {Router};