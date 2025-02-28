def home_res():
    """
    Master Oogway's Welcome Page with Styled HTML
    """
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Master Oogway's Monitoring Service</title>
        <style>
            body {
                font-family: 'Arial', sans-serif;
                background-color: #f4f4f4;
                color: #333;
                text-align: center;
                padding: 40px;
            }
            .container {
                max-width: 800px;
                margin: auto;
                padding: 20px;
                background: white;
                box-shadow: 0px 4px 8px rgba(0, 0, 0, 0.2);
                border-radius: 10px;
            }
            h1 {
                color: #2c3e50;
                font-size: 28px;
                text-decoration: underline;
            }
            p {
                font-size: 18px;
                line-height: 1.6;
            }
            .highlight {
                color: #e74c3c;
                font-weight: bold;
            }
            .emoji {
                font-size: 24px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🐢 Master Oogway's Monitoring Service 🖥️</h1>
            <p>
                "I once sent my student on a <span class="highlight">critical production monitoring mission</span>, 
                but instead of keeping an eye on the servers, he ended up binge-watching <span class="highlight">cat videos</span>! 🐱💻
            </p>
            <p>
                Turns out, '<span class="highlight">watchdog</span>' took on a whole new meaning! 😂
                Now, I am stepping in to teach <span class="highlight">Shifu</span> the true art of monitoring.
            </p>
            <p>
                From taming runaway alerts to ensuring our systems stay as smooth as a well-oiled server farm, 
                there will be <span class="highlight">no more unexpected downtimes</span> or mysterious 404s! 🚀🔧📈
            </p>
            <p>
                <b>Oogway is now installed on Nammayatri!</b> 🏎️✨
            </p>
            <p class="emoji">🐢💡 <i>“The present is a gift, and so is good observability.”</i></p>
        </div>
    </body>
    </html>
    """