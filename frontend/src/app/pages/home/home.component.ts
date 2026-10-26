import { Component, OnDestroy, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

interface HeroSlide {
  src: string;
  alt: string;
  objectPosition: string;
}

@Component({
  selector: 'app-home',
  imports: [RouterLink],
  templateUrl: './home.component.html',
  styleUrl: './home.component.css',
  host: {
    '(mouseenter)': 'pauseAutoplay()',
    '(mouseleave)': 'resumeAutoplay()',
    '(focusin)': 'pauseAutoplay()',
    '(focusout)': 'resumeAutoplay()',
  },
})
export class HomeComponent implements OnInit, OnDestroy {
  protected readonly currentSlide = signal(0);
  protected readonly slides: readonly HeroSlide[] = [
    {
      src: '/images/usables/foto1.jpg',
      alt: 'Vehículo recolector azul prestando el servicio de aseo en Armenia',
      objectPosition: 'center 54%',
    },
    {
      src: '/images/usables/foto2.jpeg',
      alt: 'Vehículo recolector con identidad ambiental de Armenia',
      objectPosition: 'center 52%',
    },
    {
      src: '/images/usables/foto3.jpg',
      alt: 'Flota de vehículos recolectores en un sector residencial de Armenia',
      objectPosition: 'center 57%',
    },
    {
      src: '/images/usables/foto4.jpeg',
      alt: 'Equipo de aseo operando un vehículo recolector en Armenia',
      objectPosition: 'center 65%',
    },
  ];

  private autoplayTimer?: ReturnType<typeof setInterval>;
  private readonly autoplayDelay = 5000;

  ngOnInit(): void {
    this.startAutoplay();
  }

  ngOnDestroy(): void {
    this.stopAutoplay();
  }

  protected previousSlide(): void {
    const previous =
      (this.currentSlide() - 1 + this.slides.length) % this.slides.length;
    this.selectSlide(previous);
  }

  protected nextSlide(): void {
    this.selectSlide((this.currentSlide() + 1) % this.slides.length);
  }

  protected selectSlide(index: number): void {
    this.currentSlide.set(index);
    this.restartAutoplay();
  }

  protected pauseAutoplay(): void {
    this.stopAutoplay();
  }

  protected resumeAutoplay(): void {
    this.startAutoplay();
  }

  private startAutoplay(): void {
    if (this.autoplayTimer || this.prefersReducedMotion()) {
      return;
    }

    this.autoplayTimer = setInterval(() => {
      this.currentSlide.update((index) => (index + 1) % this.slides.length);
    }, this.autoplayDelay);
  }

  private stopAutoplay(): void {
    if (!this.autoplayTimer) {
      return;
    }

    clearInterval(this.autoplayTimer);
    this.autoplayTimer = undefined;
  }

  private restartAutoplay(): void {
    this.stopAutoplay();
    this.startAutoplay();
  }

  private prefersReducedMotion(): boolean {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }
}
