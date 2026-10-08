// Tailwind theme shared by every VidyaPath page (loaded right after the Tailwind CDN script)
tailwind.config = {
    theme: {
        extend: {
            fontFamily: {
                sans: ['Space Mono', 'monospace'],
                display: ['Archivo Black', 'sans-serif'],
            },
            colors: {
                'neo-yellow': '#FFF500',
                'neo-pink': '#FF00D6',
                'neo-blue': '#00F0FF',
                'neo-black': '#121212',
                'neo-red': '#FF2A00',
                'neo-green': '#00E676',
            },
            boxShadow: {
                'brutal': '8px 8px 0px 0px #000000',
                'brutal-sm': '4px 4px 0px 0px #000000',
            }
        }
    }
};
