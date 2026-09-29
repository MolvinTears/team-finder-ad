// Header sidebar toggle logic
(function(){
  document.addEventListener("DOMContentLoaded", function() {
    const userMenu = document.querySelector('.user-menu');
    const sidebar = document.getElementById('userSidebar');
    const overlay = document.getElementById('sidebarOverlay');

    if (!userMenu || !sidebar || !overlay) return;

    function openSidebar() {
      sidebar.classList.add('show');
      userMenu.setAttribute('aria-expanded', 'true');
      overlay.classList.add('show');
    }

    function closeSidebar() {
      sidebar.classList.remove('show');
      userMenu.setAttribute('aria-expanded', 'false');
      overlay.classList.remove('show');
    }

    document.addEventListener('keydown', e => { if (e.key === 'Escape') closeSidebar(); });

    userMenu.addEventListener('click', (e) => {
      e.stopPropagation();
      openSidebar();
    });

    document.addEventListener('click', (e) => {
      const isClickInside = sidebar.contains(e.target) || userMenu.contains(e.target);
      if (!isClickInside && sidebar.classList.contains('show')) {
        closeSidebar();
      }
    });
  });
})();
