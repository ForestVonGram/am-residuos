import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

interface FrequentlyAskedQuestion {
  question: string;
  answer: string;
}

@Component({
  selector: 'app-help',
  imports: [RouterLink],
  templateUrl: './help.component.html',
  styleUrl: './help.component.css',
})
export class HelpComponent {
  protected readonly questions: readonly FrequentlyAskedQuestion[] = [
    {
      question: '¿Cómo consulto el horario de recolección de mi sector?',
      answer:
        'Ingresa al módulo de rutas, selecciona tu sector y consulta la jornada y el horario programados para la recolección.',
    },
    {
      question: '¿Cómo identifico la ruta que corresponde a mi ubicación?',
      answer:
        'En la consulta de rutas podrás ubicar tu sector en el mapa y revisar el recorrido asignado. Verifica que la dirección o el sector seleccionados sean correctos.',
    },
    {
      question: '¿Qué significa el tiempo estimado de llegada?',
      answer:
        'Es una proyección de la hora en la que el vehículo recolector llegará a tu sector. Puede cambiar por el tráfico, novedades operativas o ajustes en el recorrido.',
    },
    {
      question: '¿Por qué no puedo ver la ubicación del vehículo?',
      answer:
        'La ubicación se muestra cuando la ruta está activa y el dispositivo GPS tiene conexión. Si no aparece, es posible que la jornada aún no haya comenzado o exista una interrupción temporal.',
    },
    {
      question: '¿Cómo puedo reportar una novedad o presentar una PQRS?',
      answer:
        'Utiliza el canal de PQRS para describir la situación y proporcionar los datos necesarios para su seguimiento. También puedes comunicarte mediante los datos de contacto disponibles al final de la página.',
    },
    {
      question: '¿Necesito crear una cuenta para consultar las rutas?',
      answer:
        'No. La información ciudadana sobre rutas, horarios y tiempos estimados está pensada para consultarse de manera sencilla. Las funciones administrativas sí requieren acceso autorizado.',
    },
  ];
}
