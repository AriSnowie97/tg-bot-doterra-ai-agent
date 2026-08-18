const ChatSvg = ({className}) => {
    return (
        <>
            <svg
            className={className}
            // width="20"
            // height="20"
            viewBox="0 0 24 24"
            fill="none"
            >
                <path
                d="M4 4h16v12H8l-4 4V4z"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinejoin="round"
                />
            </svg>
        </>
    );
};

export {ChatSvg}