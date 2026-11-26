class Pago(models.Model):
    fecha = models.DateField()
    alumno = models.ForeignKey('Alumno', on_delete=models.CASCADE)
    curso = models.ManyToManyField('Curso')
    auxiliar = models.ForeignKey('Personal', on_delete=models.CASCADE)

    def __str__(self):
        return f"Pago del {self.fecha} para {self.Alumno} por el curso {self.Curso}"


class DetallePago(models.Model):
    pago = models.ForeignKey(Pago, on_delete=models.CASCADE)
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE)
    cantidad = models.IntegerField(default=1, max_length=2)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    observaciones = models.CharField(max_length=100, verbose_name="Observaciones", null=True, blank=True)
    precio_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
