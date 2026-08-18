const ContactsSvg = ({className}) => {
    return (
        <>
            <svg
            className={className}
            viewBox="0 0 24 24"
            fill="none"
            >
                <circle
                cx="12"
                cy="8"
                r="4"
                stroke="currentColor"
                strokeWidth="2"
                />
                <path
                d="M4 20c0-4 3.5-6 8-6s8 2 8 6"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                />
            </svg>
        </>
    );
};

export {ContactsSvg}