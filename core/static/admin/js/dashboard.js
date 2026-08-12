(function () {
  'use strict';

  var app = document.getElementById('dashboard-app');
  if (!app) return;

  function formatDate(iso) {
    if (!iso) return '';
    var d = new Date(iso);
    return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' }) + ' ' +
      d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
  }

  function timeAgo(iso) {
    if (!iso) return '';
    var diff = Date.now() - new Date(iso).getTime();
    var mins = Math.floor(diff / 60000);
    if (mins < 1) return 'agora';
    if (mins < 60) return mins + ' min atrás';
    var hours = Math.floor(mins / 60);
    if (hours < 24) return hours + 'h atrás';
    var days = Math.floor(hours / 24);
    if (days < 7) return days + 'd atrás';
    return formatDate(iso);
  }

  function getInitials(name) {
    if (!name) return '?';
    var parts = name.split(/[\s.]+/);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return name.substring(0, 2).toUpperCase();
  }

  var iconMap = {
    'total_usuarios': { icon: 'fa-users', color: 'blue', accent: 'blue' },
    'novos_semana': { icon: 'fa-user-plus', color: 'green', accent: 'green' },
    'cursos_ativos': { icon: 'fa-video', color: 'orange', accent: 'orange' },
    'videos_ativos': { icon: 'fa-play', color: 'pink', accent: 'pink' },
    'eventos_futuros': { icon: 'fa-calendar', color: 'purple', accent: 'purple' },
    'trilhas_publicadas': { icon: 'fa-route', color: 'cyan', accent: 'cyan' },
  };

  var metricLabels = {
    'total_usuarios': 'Usuários',
    'novos_semana': 'Novos (7 dias)',
    'cursos_ativos': 'Cursos Ativos',
    'videos_ativos': 'Vídeos Ativos',
    'eventos_futuros': 'Eventos Futuros',
    'trilhas_publicadas': 'Trilhas',
  };

  function renderMetrics(metricas) {
    var html = '<h1 class="dashboard-section-title"><img src="/static/admin/images/metrica.svg" alt="" class="metric-title-icon"> Métricas Rápidas<span class="dashboard-section-title--sub">Resumo do estado atual da plataforma</span></h1>';
    html += '<div class="dashboard-metrics">';

    var keys = ['total_usuarios', 'novos_semana', 'cursos_ativos', 'videos_ativos', 'eventos_futuros', 'trilhas_publicadas'];

    keys.forEach(function (key) {
      var cfg = iconMap[key] || { icon: 'fa-chart-simple', color: 'blue' };
      var value = metricas[key] || 0;
      html += '<div class="metric-card">';
      html += '  <div class="metric-card__icon metric-card__icon--' + cfg.color + '"><i class="fa-solid ' + cfg.icon + '"></i></div>';
      html += '  <div class="metric-card__value" data-final="' + value + '">0</div>';
      html += '  <div class="metric-card__label">' + (metricLabels[key] || key) + '</div>';
      html += '</div>';
    });

    html += '</div>';
    return html;
  }

  function renderChart(crescimento) {
    if (!crescimento || crescimento.length === 0) {
      return '<div class="dashboard-chart"><p style="color:var(--text-muted);text-align:center;padding:40px">Sem dados de crescimento ainda</p></div>';
    }

    var labels = crescimento.map(function (m) { return m.label; });
    var valores = crescimento.map(function (m) { return m.total; });
    var acumulado = crescimento.map(function (m) { return m.acumulado || 0; });
    var totalGeral = acumulado.length > 0 ? acumulado[acumulado.length - 1] : 0;
    var ultimosValores = valores.slice(-3);
    var media = Math.round(ultimosValores.reduce(function(a, b) { return a + b; }, 0) / ultimosValores.length);

    var html = '<div class="dashboard-chart">';
    html += '  <div class="dashboard-chart__header">';
    html += '    <div class="dashboard-chart__title-group">';
    html += '      <h3 class="dashboard-chart__title">📈 Crescimento de Usuários</h3>';
    html += '      <div class="dashboard-chart__legend">';
    html += '        <span class="dashboard-chart__legend-item"><span class="dashboard-chart__legend-dot" style="background:#ff9d00"></span>Novos</span>';
    html += '        <span class="dashboard-chart__legend-item"><span class="dashboard-chart__legend-dot" style="background:#3b82f6"></span>Acumulado</span>';
    html += '      </div>';
    html += '    </div>';
    html += '    <div class="dashboard-chart__stats">';
    html += '      <div class="dashboard-chart__stat">';
    html += '        <div class="dashboard-chart__stat-value">' + totalGeral + '</div>';
    html += '        <div class="dashboard-chart__stat-label">Total</div>';
    html += '      </div>';
    html += '      <div class="dashboard-chart__stat">';
    html += '        <div class="dashboard-chart__stat-value">' + media + '</div>';
    html += '        <div class="dashboard-chart__stat-label">Média (3m)</div>';
    html += '      </div>';
    html += '      <div class="dashboard-chart__stat">';
    html += '        <div class="dashboard-chart__stat-value">' + valores.length + '</div>';
    html += '        <div class="dashboard-chart__stat-label">Meses</div>';
    html += '      </div>';
    html += '    </div>';
    html += '  </div>';
    html += '  <div class="dashboard-chart__canvas">';
    html += '    <canvas id="userGrowthChart"></canvas>';
    html += '  </div>';
    html += '</div>';

    setTimeout(function () {
      var ctx = document.getElementById('userGrowthChart');
      if (!ctx) return;
      var grad1 = ctx.getContext('2d').createLinearGradient(0, 0, 0, 280);
      grad1.addColorStop(0, 'rgba(255, 157, 0, 0.25)');
      grad1.addColorStop(0.5, 'rgba(255, 157, 0, 0.08)');
      grad1.addColorStop(1, 'rgba(255, 157, 0, 0.01)');

      var grad2 = ctx.getContext('2d').createLinearGradient(0, 0, 0, 280);
      grad2.addColorStop(0, 'rgba(59, 130, 246, 0.15)');
      grad2.addColorStop(0.5, 'rgba(59, 130, 246, 0.05)');
      grad2.addColorStop(1, 'rgba(59, 130, 246, 0.01)');

      new Chart(ctx, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [
            {
              label: 'Novos Usuários',
              data: valores,
              borderColor: '#ff9d00',
              backgroundColor: grad1,
              fill: true,
              tension: 0.35,
              pointBackgroundColor: '#ff9d00',
              pointBorderColor: '#0d1f3c',
              pointBorderWidth: 2,
              pointRadius: 4,
              pointHoverRadius: 7,
              pointHoverBorderWidth: 3,
              borderWidth: 2.5,
            },
            {
              label: 'Acumulado',
              data: acumulado,
              borderColor: '#3b82f6',
              backgroundColor: grad2,
              fill: true,
              tension: 0.35,
              pointBackgroundColor: '#3b82f6',
              pointBorderColor: '#0d1f3c',
              pointBorderWidth: 2,
              pointRadius: 4,
              pointHoverRadius: 7,
              pointHoverBorderWidth: 3,
              borderWidth: 2.5,
              yAxisID: 'y1',
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: {
            duration: 1200,
            easing: 'easeOutQuart',
          },
          interaction: {
            intersect: false,
            mode: 'index',
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: '#0d1f3c',
              titleColor: '#fff',
              bodyColor: '#8b9ab5',
              borderColor: '#1e3350',
              borderWidth: 1,
              padding: 14,
              cornerRadius: 10,
              boxPadding: 4,
              usePointStyle: true,
              callbacks: {
                label: function (ctx) {
                  return ctx.dataset.label + ': ' + ctx.parsed.y;
                }
              }
            }
          },
          scales: {
            x: {
              grid: { color: 'rgba(255,255,255,0.03)', drawBorder: false },
              ticks: { color: '#4a5568', font: { size: 11, family: 'DM Sans' } },
            },
            y: {
              beginAtZero: true,
              grid: { color: 'rgba(255,255,255,0.03)', drawBorder: false },
              ticks: {
                color: '#4a5568',
                font: { size: 11, family: 'DM Sans' },
                stepSize: 1,
                padding: 8,
              },
              title: { display: true, text: 'Novos', color: '#4a5568', font: { size: 11, family: 'DM Sans' } }
            },
            y1: {
              position: 'right',
              beginAtZero: true,
              grid: { display: false },
              ticks: {
                color: '#4a5568',
                font: { size: 11, family: 'DM Sans' },
                padding: 8,
              },
              title: { display: true, text: 'Total', color: '#4a5568', font: { size: 11, family: 'DM Sans' } }
            }
          }
        }
      });
    }, 50);

    return html;
  }

  function renderEventosChart(eventosLeituras) {
    var porEvento = (eventosLeituras && eventosLeituras.por_evento) || [];
    var totalUsuarios = (eventosLeituras && eventosLeituras.total_usuarios) || 0;
    var totalLeituras = (eventosLeituras && eventosLeituras.total_leituras) || 0;

    if (porEvento.length === 0) {
      return '<div class="dashboard-chart"><p style="color:var(--text-muted);text-align:center;padding:40px">Sem dados de acompanhamento ainda</p></div>';
    }

    function truncar(txt, max) {
      if (!txt) return '';
      return txt.length > max ? txt.substring(0, max - 1) + '…' : txt;
    }

    var labels = porEvento.map(function (e) { return truncar(e.evento, 24); });
    var valores = porEvento.map(function (e) { return e.usuarios; });

    var html = '<div class="dashboard-chart">';
    html += '  <div class="dashboard-chart__header">';
    html += '    <div class="dashboard-chart__title-group">';
    html += '      <h3 class="dashboard-chart__title"> Quantos usuários acompanham os eventos?</h3>';
    html += '      <div class="dashboard-chart__legend">';
    html += '        <span class="dashboard-chart__legend-item"><span class="dashboard-chart__legend-dot" style="background:#a855f7"></span>Usuários</span>';
    html += '      </div>';
    html += '    </div>';
    html += '    <div class="dashboard-chart__stats">';
    html += '      <div class="dashboard-chart__stat">';
    html += '        <div class="dashboard-chart__stat-value">' + totalUsuarios + '</div>';
    html += '        <div class="dashboard-chart__stat-label">Usuários</div>';
    html += '      </div>';
    html += '      <div class="dashboard-chart__stat">';
    html += '        <div class="dashboard-chart__stat-value">' + totalLeituras + '</div>';
    html += '        <div class="dashboard-chart__stat-label">Leituras</div>';
    html += '      </div>';
    html += '      <div class="dashboard-chart__stat">';
    html += '        <div class="dashboard-chart__stat-value">' + porEvento.length + '</div>';
    html += '        <div class="dashboard-chart__stat-label">Eventos</div>';
    html += '      </div>';
    html += '    </div>';
    html += '  </div>';
    html += '  <div class="dashboard-chart__canvas">';
    html += '    <canvas id="eventosChart"></canvas>';
    html += '  </div>';
    html += '</div>';

    setTimeout(function () {
      var ctx = document.getElementById('eventosChart');
      if (!ctx) return;
      var grad = ctx.getContext('2d').createLinearGradient(0, 0, 0, 280);
      grad.addColorStop(0, 'rgba(168, 85, 247, 0.5)');
      grad.addColorStop(1, 'rgba(168, 85, 247, 0.15)');

      new Chart(ctx, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [
            {
              label: 'Usuários',
              data: valores,
              backgroundColor: grad,
              borderColor: '#a855f7',
              borderWidth: 1.5,
              borderRadius: 8,
              maxBarThickness: 48,
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: {
            duration: 1200,
            easing: 'easeOutQuart',
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: '#0d1f3c',
              titleColor: '#fff',
              bodyColor: '#8b9ab5',
              borderColor: '#1e3350',
              borderWidth: 1,
              padding: 14,
              cornerRadius: 10,
              boxPadding: 4,
              usePointStyle: true,
              callbacks: {
                title: function (items) {
                  var idx = items.length ? items[0].dataIndex : 0;
                  return porEvento[idx].evento;
                },
                label: function (ctx) {
                  var item = porEvento[ctx.dataIndex];
                  return ctx.parsed.y + ' usuário(s) • ' + item.leituras + ' leitura(s)';
                }
              }
            }
          },
          scales: {
            x: {
              grid: { display: false },
              ticks: { color: '#4a5568', font: { size: 11, family: 'DM Sans' }, maxRotation: 40, minRotation: 0 },
            },
            y: {
              beginAtZero: true,
              grid: { color: 'rgba(255,255,255,0.03)', drawBorder: false },
              ticks: {
                color: '#4a5568',
                font: { size: 11, family: 'DM Sans' },
                stepSize: 1,
                padding: 8,
              },
              title: { display: true, text: 'Usuários', color: '#4a5568', font: { size: 11, family: 'DM Sans' } }
            }
          }
        }
      });
    }, 50);

    return html;
  }

  function renderFeed(atividades) {
    var html = '<div class="dashboard-feed">';
    html += '  <h3 class="highlight-card__title"><i class="fa-solid fa-clock-rotate-left"></i> Últimas Atividades</h3>';
    html += '  <div class="dashboard-feed__list">';

    if (!atividades || atividades.length === 0) {
      html += '    <div class="feed-empty">';
      html += '      <div><i class="fa-solid fa-inbox"></i></div>';
      html += '      <p>Nenhuma atividade registrada ainda</p>';
      html += '    </div>';
    } else {
      atividades.forEach(function (log) {
        var nome = log.usuario_nome || 'Sistema';
        html += '    <div class="feed-item">';
        html += '      <div class="feed-item__avatar feed-item__avatar--active">' + getInitials(nome) + '</div>';
        html += '      <div class="feed-item__body">';
        html += '        <div class="feed-item__text"><strong>' + escapeHtml(nome) + '</strong> ' + escapeHtml(log.acao) + '</div>';
        html += '        <div class="feed-item__time"><i class="fa-regular fa-clock"></i> ' + timeAgo(log.created_at) + '</div>';
        html += '      </div>';
        html += '    </div>';
      });
    }

    html += '  </div>';
    html += '</div>';
    return html;
  }

  function escapeHtml(text) {
    if (!text) return '';
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
  }

  function renderHighlights(destaques) {
    var html = '<div class="dashboard-highlights">';

    html += '  <div class="highlight-card">';
    html += '    <h3 class="highlight-card__title"><i class="fa-solid fa-star"></i> Top Cursos</h3>';
    if (!destaques.top_cursos || destaques.top_cursos.length === 0) {
      html += '    <div class="highlight-empty">Nenhum curso publicado</div>';
    } else {
      destaques.top_cursos.forEach(function (c) {
        var badgeClass = c.status === 'publicado' ? 'status-badge--publicado' : 'status-badge--rascunho';
        html += '    <div class="highlight-item">';
        html += '      <div class="highlight-item__info">';
        html += '        <div class="highlight-item__name">' + escapeHtml(c.titulo) + '</div>';
        html += '        <div class="highlight-item__meta"><span class="status-badge ' + badgeClass + '">' + c.status + '</span></div>';
        html += '      </div>';
        html += '      <span class="highlight-item__badge highlight-item__badge--views">' + (c.total_visualizacoes || 0) + ' views</span>';
        html += '    </div>';
      });
    }
    html += '  </div>';

    html += '  <div class="highlight-card">';
    html += '    <h3 class="highlight-card__title"><i class="fa-solid fa-calendar"></i> Próximos Eventos</h3>';
    if (!destaques.proximos_eventos || destaques.proximos_eventos.length === 0) {
      html += '    <div class="highlight-empty">Nenhum evento futuro</div>';
    } else {
      destaques.proximos_eventos.forEach(function (e) {
        var data = e.data ? formatDate(e.data) : '';
        html += '    <div class="highlight-item">';
        html += '      <div class="highlight-item__info">';
        html += '        <div class="highlight-item__name">' + escapeHtml(e.titulo) + '</div>';
        html += '        <div class="highlight-item__meta">' + (e.local || 'Sem local') + '</div>';
        html += '      </div>';
        html += '      <span class="highlight-item__badge highlight-item__badge--date">' + data + '</span>';
        html += '    </div>';
      });
    }
    html += '  </div>';

    html += '  <div class="highlight-card">';
    html += '    <h3 class="highlight-card__title"><i class="fa-solid fa-route"></i> Trilhas</h3>';
    if (!destaques.top_trilhas || destaques.top_trilhas.length === 0) {
      html += '    <div class="highlight-empty">Nenhuma trilha cadastrada</div>';
    } else {
      destaques.top_trilhas.forEach(function (t) {
        html += '    <div class="highlight-item">';
        html += '      <div class="highlight-item__info">';
        html += '        <div class="highlight-item__name">' + escapeHtml(t.nome) + '</div>';
        html += '        <div class="highlight-item__meta">' + escapeHtml(t.ambiente) + '</div>';
        html += '      </div>';
        html += '      <span class="highlight-item__badge highlight-item__badge--count">' + (t.total_cursos || 0) + ' cursos</span>';
        html += '    </div>';
      });
    }
    html += '  </div>';

    html += '</div>';
    return html;
  }

  function renderAlerts(alertas) {
    var html = '<div class="dashboard-section-title">⚠️ Alertas</div>';
    html += '<div class="dashboard-alerts">';

    if (!alertas || alertas.length === 0) {
      html += '  <div class="alert-empty">';
      html += '    <div><i class="fa-solid fa-circle-check" style="color:#34d399"></i></div>';
      html += '    <p>Tudo certo! Nenhum alerta no momento.</p>';
      html += '  </div>';
    } else {
      var icons = { warning: 'fa-triangle-exclamation', info: 'fa-circle-info', danger: 'fa-circle-exclamation' };
      alertas.forEach(function (a) {
        var tipo = a.tipo || 'info';
        var icon = icons[tipo] || 'fa-circle-info';
        html += '  <div class="alert-item alert-item--' + tipo + '">';
        html += '    <i class="fa-solid ' + icon + ' alert-item__icon"></i>';
        html += '    <span class="alert-item__text">' + escapeHtml(a.mensagem) + '</span>';
        html += '  </div>';
      });
    }

    html += '</div>';
    return html;
  }

  function animateCounters() {
    var elements = document.querySelectorAll('.metric-card__value');
    elements.forEach(function (el) {
      var finalVal = parseInt(el.getAttribute('data-final'), 10) || 0;
      el.textContent = '0';
      var duration = 1200;
      var startTime = null;

      function step(timestamp) {
        if (!startTime) startTime = timestamp;
        var progress = Math.min((timestamp - startTime) / duration, 1);
        var eased = 1 - Math.pow(1 - progress, 3);
        el.textContent = Math.floor(eased * finalVal);
        if (progress < 1) {
          requestAnimationFrame(step);
        } else {
          el.textContent = finalVal;
        }
      }

      requestAnimationFrame(step);
    });
  }

  function observeMetrics() {
    var grid = document.querySelector('.dashboard-metrics');
    if (!grid) return;

    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          animateCounters();
        }
      });
    }, { threshold: 0.3 });

    observer.observe(grid);
  }

  function buildDashboard(data) {
    var html = '<div class="dashboard">';
    html += renderMetrics(data.metricas || {});
    html += renderChart(data.crescimento_usuarios || []);
    html += renderEventosChart(data.eventos_leituras || {});
    html += '<div class="dashboard-columns">';
    html += renderFeed(data.ultimas_atividades || []);
    html += renderHighlights(data.destaques || {});
    html += '</div>';
    html += renderAlerts(data.alertas || []);
    html += '</div>';
    app.innerHTML = html;
    animateCounters();
    observeMetrics();
  }

  function fetchDashboard() {
    fetch('/api/dashboard-data/')
      .then(function (r) {
        if (!r.ok) throw new Error('Erro HTTP ' + r.status);
        return r.json();
      })
      .then(buildDashboard)
      .catch(function (err) {
        app.innerHTML =
          '<div class="dashboard-loading" style="color:#f87171">' +
          '<i class="fa-solid fa-circle-exclamation" style="font-size:32px"></i>' +
          '<p>Erro ao carregar dashboard: ' + err.message + '</p>' +
          '</div>';
      });
  }

  fetchDashboard();
})();