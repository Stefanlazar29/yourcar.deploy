const pageLanding  = document.getElementById('page-landing');
const pageBenefits = document.getElementById('page-benefits');

function showBenefits() {
  pageLanding.classList.remove('active');
  pageBenefits.classList.add('active');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function showLanding() {
  pageBenefits.classList.remove('active');
  pageLanding.classList.add('active');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function goLogin() {
  window.location.href = '/mulberry_app.html';
}

document.getElementById('btn-inscrie-nav').addEventListener('click', showBenefits);
document.getElementById('btn-inscrie-hero').addEventListener('click', showBenefits);
document.getElementById('btn-inscrie-p2').addEventListener('click', showBenefits);
document.getElementById('btn-inscrie-cta').addEventListener('click', function () {
  window.location.href = '/mulberry_app.html?signup=service';
});

document.getElementById('btn-login-nav').addEventListener('click', goLogin);
document.getElementById('btn-login-hero').addEventListener('click', goLogin);

document.getElementById('btn-back').addEventListener('click', showLanding);

document.getElementById('btn-contact-cta').addEventListener('click', function () {
  window.location.href = 'mailto:contact@mulberry.autos?subject=Parteneriat service';
});
