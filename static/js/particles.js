const canvas = document.getElementById('canvas-bg');
const ctx = canvas.getContext('2d');

canvas.width = window.innerWidth;
canvas.height = window.innerHeight;

let particlesArray;

class Particle {
    constructor(x, y, directionX, directionY, size, color) {
        this.x = x;
        this.y = y;
        this.directionX = directionX;
        this.directionY = directionY;
        this.size = size;
        this.color = color;
    }

    draw() {
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2, false);
        ctx.fillStyle = 'rgba(121, 192, 255, 0.5)'; // Aumentei um pouco a opacidade para destacar
        ctx.fill();
    }

    update() {
        if (this.x > canvas.width || this.x < 0) {
            this.directionX = -this.directionX;
        }
        if (this.y > canvas.height || this.y < 0) {
            this.directionY = -this.directionY;
        }
        this.x += this.directionX;
        this.y += this.directionY;
        this.draw();
    }
}

// Função para conectar as partículas e criar o feixe
function connect() {
    let opacityValue = 1;
    for (let a = 0; a < particlesArray.length; a++) {
        for (let b = a; b < particlesArray.length; b++) {
            let dx = particlesArray[a].x - particlesArray[b].x;
            let dy = particlesArray[a].y - particlesArray[b].y;
            let distance = Math.sqrt(dx * dx + dy * dy);

            // Se as bolinhas estiverem perto (conexão de rede)
            if (distance < 100) {
                opacityValue = 1 - (distance / 100);
                ctx.strokeStyle = `rgba(121, 192, 255, ${opacityValue})`;
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(particlesArray[a].x, particlesArray[a].y);
                ctx.lineTo(particlesArray[b].x, particlesArray[b].y);
                ctx.stroke();

                // EFEITO DO FEIXE: Se elas quase se tocarem, solta o feixe vertical
                if (distance < 20) {
                    let beamGradient = ctx.createLinearGradient(0, particlesArray[a].y, 0, 0);
                    beamGradient.addColorStop(0, `rgba(255, 255, 255, ${opacityValue})`);
                    beamGradient.addColorStop(1, 'rgba(121, 192, 255, 0)');
                    
                    ctx.strokeStyle = beamGradient;
                    ctx.lineWidth = 2;
                    ctx.beginPath();
                    ctx.moveTo(particlesArray[a].x, particlesArray[a].y);
                    ctx.lineTo(particlesArray[a].x, 0); // O feixe sobe até o topo
                    ctx.stroke();
                }
            }
        }
    }
}

function init() {
    particlesArray = [];
    // Reduzi um pouco a densidade para não poluir demais com muitos feixes
    let numberOfParticles = (canvas.height * canvas.width) / 15000; 
    for (let i = 0; i < numberOfParticles; i++) {
        let size = (Math.random() * 3) + 2;
        let x = (Math.random() * ((innerWidth - size * 2) - (size * 2)) + size * 2);
        let y = (Math.random() * ((innerHeight - size * 2) - (size * 2)) + size * 2);
        let directionX = (Math.random() * 1) - 0.5;
        let directionY = (Math.random() * 1) - 0.5;
        let color = '#79c0ff';

        particlesArray.push(new Particle(x, y, directionX, directionY, size, color));
    }
}

function animate() {
    requestAnimationFrame(animate);
    ctx.clearRect(0, 0, innerWidth, innerHeight);
    
    for (let i = 0; i < particlesArray.length; i++) {
        particlesArray[i].update();
    }
    connect(); // Chama a função que faz o encontro e os feixes
}

window.addEventListener('resize', () => {
    canvas.width = innerWidth;
    canvas.height = innerHeight;
    init();
});

init();
animate();