{% load static %}
<script src="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.0/js/bootstrap.bundle.min.js"></script>
                <script>
                    // Real-time clock

                    function updateClock() {
                        const now = new Date();
                        const timeString = now.toLocaleTimeString('en-GB', {
                            hour: '2-digit',
                            minute: '2-digit',
                            second: '2-digit',
                            hour12: false
                        });
                        const dateString = now.toLocaleDateString('en-GB', {
                            weekday: 'long',
                            year: 'numeric',
                            month: 'long',
                            day: 'numeric'
                        });

                        document.getElementById('currentTime').innerHTML = `
                                        <div>${timeString}</div>
                                        <small class="text-muted">${dateString}</small>
                                    `;
                    }

                    // Handle card clicks
                    function handleCardClick(cardName) {
                        alert(`${cardName} selected! This would navigate to the ${cardName.toLowerCase()} page in a real application.`);
                    }

                    // Logout function
                    function logout() {
                        if (confirm('Are you sure you want to logout?')) {
                            alert('Logout successful! Thank you for your service.');
                            // In a real application, this would redirect to login page
                        }
                    }

                    // Initialize clock
                    updateClock();
                    setInterval(updateClock, 1000);

                    // Add some interactive feedback
                    document.querySelectorAll('.function-card').forEach(card => {
                        card.addEventListener('mouseenter', function () {
                            this.style.background = 'linear-gradient(135deg, #7CB9E8 40%, #f8f9ff 100%)';
                        });

                        card.addEventListener('mouseleave', function () {
                            this.style.background = 'white';
                        });
                    });

                </script>