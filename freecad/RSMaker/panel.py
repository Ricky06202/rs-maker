"""FreeCAD native assistant: all five puzzles always present."""
import os
from dataclasses import replace
from .config import (PuzzleConfig, PUZZLES, DIFFICULTIES, FACES, THEMES,
                     DIAL_MARKS, MECHANISM_FOR_FACE)
from .collection import (COLLECTIONS, FIGURES, SCENES, EXPRESSIONS,
                         COLLECTION_OPTIONS, COLLECTION_DEFAULTS)
from .project import create_project, regenerate_project, config_from_project
try:
    from PySide import QtWidgets
except ImportError:
    from PySide2 import QtWidgets

FIELD_BY_FACE = {"Frontal":"frontal", "Derecha":"derecha", "Trasera":"trasera",
                 "Izquierda":"izquierda", "Tapa":"tapa"}


class PuzzleDialog(QtWidgets.QDialog):
    def __init__(self, root=None,parent=None):
        super().__init__(parent)
        self.root = root
        self.setWindowTitle("RS Maker 0.4 | "+("Editar caja" if root else "Nueva caja de cinco puzzles"))
        self.setMinimumWidth(530)
        self.resize(620,750)
        self.setModal(False)
        self.build_ui()
        self.fill_from_config(config_from_project(root) if root else replace(
            PuzzleConfig(), collection="Comida", figure="Hamburguesita",
            scene="Restaurante", theme="Ninguno"))
        self.update_preview()

    def build_ui(self):
        main = QtWidgets.QVBoxLayout(self)
        heading=QtWidgets.QLabel("Caja puzzle sorpresa · Cinco retos obligatorios")
        heading.setStyleSheet("font-size: 17px; font-weight: 600;")
        main.addWidget(heading)
        note=QtWidgets.QLabel(
            "Cuatro laterales: gira una rueda o baja una compuerta según "
            "el mecanismo elegido, y luego desliza cada cerrojo. "
            "Finalmente gira la leva de la tapa para liberar el quinto cierre.")
        note.setWordWrap(True)
        main.addWidget(note)
        scroll=QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        container=QtWidgets.QWidget()
        body=QtWidgets.QVBoxLayout(container)

        lib=QtWidgets.QGroupBox("Biblioteca de mecanismos · 4 laterales")
        lib_form=QtWidgets.QFormLayout(lib)
        self.mechanisms={}
        for face in FACES[:4]:
            mechanism=QtWidgets.QComboBox()
            for key,item in PUZZLES.items():
                if not item["implemented"]:
                    continue
                mechanism.addItem(item["name"],key)
            mechanism.setToolTip(
                "Rueda: girar y retirar cerrojo. Secuencia: bajar "
                "compuerta 12 mm y después retirar cerrojo 20 mm. "
                "La leva de la tapa se conserva siempre.")
            self.mechanisms[MECHANISM_FOR_FACE[face]]=mechanism
            lib_form.addRow(face,mechanism)
        top_info=QtWidgets.QLabel(
            "Cuatro retos laterales independientes; la tapa conserva "
            "la quinta leva. Los mecanismos siguen siendo prototipos "
            "sin validación de montaje impreso.")
        top_info.setWordWrap(True)
        lib_form.addRow(top_info)
        body.addWidget(lib)

        difficulties=QtWidgets.QGroupBox("Dificultad independiente por cara")
        dform=QtWidgets.QFormLayout(difficulties)
        self.faces={}
        for face in FACES:
            chooser=QtWidgets.QComboBox()
            for label in DIFFICULTIES:
                chooser.addItem("%s · %d marcas"%(label,DIAL_MARKS[label]),label)
            chooser.setToolTip("Cambian las marcas y la geometría del bloqueo; "
                               "la dificultad de juego no está validada con niños")
            self.faces[FIELD_BY_FACE[face]]=chooser
            dform.addRow(face,chooser)
        body.addWidget(difficulties)

        dimensions=QtWidgets.QGroupBox("Medidas de fabricación (mm)")
        dform=QtWidgets.QFormLayout(dimensions)
        specs=(("width","Ancho",170,150,320),("depth","Fondo",160,150,320),
               ("height","Alto",95,75,240),("wall","Pared",5.5,5,9),
               ("floor","Suelo",4,3,9),("clearance","Holgura nominal",.35,.2,.65))
        self.sizes={}
        for name,label,default,mn,mx in specs:
            inp=QtWidgets.QDoubleSpinBox()
            inp.setRange(mn,mx)
            inp.setDecimals(2)
            inp.setSingleStep(.05 if name=="clearance" else .5)
            inp.setSuffix(" mm")
            inp.setValue(default)
            self.sizes[name]=inp
            dform.addRow(label,inp)
        body.addWidget(dimensions)

        creative=QtWidgets.QGroupBox("Colección original · Chibi + escenario superior")
        cform=QtWidgets.QFormLayout(creative)
        self.collection=QtWidgets.QComboBox()
        for value in COLLECTIONS:self.collection.addItem(value,value)
        self.figure=QtWidgets.QComboBox()
        for value in FIGURES:self.figure.addItem(value,value)
        self.scene=QtWidgets.QComboBox()
        for value in SCENES:self.scene.addItem(value,value)
        self.expression=QtWidgets.QComboBox()
        for value in EXPRESSIONS:self.expression.addItem(value,value)
        self.figure_height=QtWidgets.QDoubleSpinBox()
        self.figure_height.setRange(25,40)
        self.figure_height.setDecimals(1)
        self.figure_height.setSuffix(" mm")
        cform.addRow("Colección",self.collection)
        cform.addRow("Muñeco coleccionable",self.figure)
        cform.addRow("Expresión grabada",self.expression)
        cform.addRow("Altura del muñeco",self.figure_height)
        cform.addRow("Decoración grande de tapa",self.scene)
        tip=QtWidgets.QLabel(
            "Comida, Espacio y Playa incluyen relieves en las cuatro caras, "
            "un personaje original dentro y una escena grande en la tapa, "
            "sin sustituir el quinto puzzle superior.")
        tip.setWordWrap(True)
        cform.addRow(tip)
        body.addWidget(creative)

        decor=QtWidgets.QGroupBox("Motivo geométrico para cajas sin colección")
        decorform=QtWidgets.QFormLayout(decor)
        self.theme=QtWidgets.QComboBox()
        for name in THEMES:self.theme.addItem(name,name)
        decorform.addRow("Motivo",self.theme)
        info=QtWidgets.QLabel("Con Comida, la decoración lateral viene incorporada; "
            "no se necesitan motivos adicionales. SVG/STL personalizados aún pendientes.")
        info.setWordWrap(True)
        decorform.addRow(info)
        body.addWidget(decor)
        scroll.setWidget(container)
        main.addWidget(scroll)

        self.preview=QtWidgets.QLabel()
        self.preview.setWordWrap(True)
        self.preview.setStyleSheet("padding: 9px; border: 1px solid gray; border-radius: 5px;")
        main.addWidget(self.preview)
        caution=QtWidgets.QLabel("Prototipo de ingeniería, no juguete listo para usar: "
                                "verifica montaje de ejes y retenedores, fuerza, holguras, "
                                "bordes, atrapamiento y riesgo de piezas pequeñas.")
        caution.setWordWrap(True)
        main.addWidget(caution)

        buttons=QtWidgets.QDialogButtonBox()
        self.create=buttons.addButton("Regenerar" if self.root else "Crear cinco puzzles",
                    QtWidgets.QDialogButtonBox.AcceptRole)
        buttons.addButton("Cancelar",QtWidgets.QDialogButtonBox.RejectRole)
        buttons.rejected.connect(self.reject)
        self.create.clicked.connect(self.generate)
        main.addWidget(buttons)
        for inp in self.sizes.values(): inp.valueChanged.connect(self.update_preview)
        for inp in self.faces.values(): inp.currentIndexChanged.connect(self.update_preview)
        for inp in self.mechanisms.values(): inp.currentIndexChanged.connect(self.update_preview)
        self.theme.currentIndexChanged.connect(self.update_preview)
        for field in (self.figure,self.scene,self.expression):
            field.currentIndexChanged.connect(self.update_preview)
        self.figure_height.valueChanged.connect(self.update_preview)
        self.collection.currentIndexChanged.connect(self.on_collection_changed)

    def fill_from_config(self,cfg):
        for name,inp in self.sizes.items(): inp.setValue(getattr(cfg,name))
        for name,inp in self.faces.items():
            pos=inp.findData(getattr(cfg,name))
            if pos >= 0: inp.setCurrentIndex(pos)
        for key in ("collection","figure","scene","expression"):
            cbo=getattr(self,key)
            index=cbo.findData(getattr(cfg,key))
            if index>=0:cbo.setCurrentIndex(index)
        self.figure_height.setValue(cfg.figure_height)
        for name,combo in self.mechanisms.items():
            index=combo.findData(getattr(cfg,name))
            if index>=0:
                combo.setCurrentIndex(index)
        ti=self.theme.findData(cfg.theme)
        if ti >= 0:self.theme.setCurrentIndex(ti)
        self.sync_collection()

    @staticmethod
    def _allowed_items(combo, values, preferred):
        old=combo.blockSignals(True)
        try:
            combo.clear()
            for value in values:
                combo.addItem(value,value)
            index=combo.findData(preferred)
            combo.setCurrentIndex(index if index>=0 else 0)
        finally:
            combo.blockSignals(old)

    def sync_collection(self, choose_defaults=False):
        collection=self.collection.currentData()
        allowed_figures,allowed_scenes=COLLECTION_OPTIONS[collection]
        defaults=COLLECTION_DEFAULTS[collection]
        desired_figure=(defaults[0] if choose_defaults else self.figure.currentData())
        desired_scene=(defaults[1] if choose_defaults else self.scene.currentData())
        self._allowed_items(self.figure,allowed_figures,desired_figure)
        self._allowed_items(self.scene,allowed_scenes,desired_scene)
        active=collection!="Ninguna"
        figure_active=active and self.figure.currentData()!="Ninguna"
        self.figure.setEnabled(active)
        self.scene.setEnabled(active)
        self.expression.setEnabled(figure_active)
        self.figure_height.setEnabled(figure_active)
        self.theme.setEnabled(not active)

    def on_collection_changed(self,*args):
        if self.collection.currentData()!="Ninguna":
            self.theme.setCurrentIndex(self.theme.findData("Ninguno"))
        self.sync_collection(choose_defaults=True)
        self.update_preview()

    def make_config(self):
        args={name:inp.value() for name,inp in self.sizes.items()}
        args.update({name:inp.currentData() for name,inp in self.faces.items()})
        args.update({name:inp.currentData() for name,inp in self.mechanisms.items()})
        args["theme"]=self.theme.currentData()
        args.update({key:getattr(self,key).currentData()
                     for key in ("collection","expression")})
        active=args["collection"]!="Ninguna"
        args["figure"]=self.figure.currentData() if active else "Ninguna"
        args["scene"]=self.scene.currentData() if active else "Ninguno"
        args["figure_height"]=self.figure_height.value()
        return PuzzleConfig(**args).validate()

    def update_preview(self,*args):
        try:
            cfg=self.make_config()
            x,y,z=cfg.prize_interior
            self.sync_collection()
            art = (" · Colección %s · Figura: %s (%.1f mm) · Escena: %s" %
                   (cfg.collection,cfg.figure,cfg.figure_height,cfg.scene)
                   if cfg.collection!="Ninguna" else " · Sin colección")
            sequence_count=sum(
                cfg.face_mechanism(face)=="secuencia" for face in FACES[:4])
            self.preview.setText(
                "5/5 caras activas · Espacio conservador del premio: "
                "%.1f × %.1f × %.1f mm.\n"
                "%d compuertas lineales y %d ruedas laterales; "
                "la leva superior permanece como quinto reto. "
                "Secuencia: bajar compuerta y luego deslizar cerrojo. "
                "Prototipo físico no validado%s."
                %(x,y,z,sequence_count,4-sequence_count,art))
            self.create.setEnabled(True)
        except ValueError as exc:
            self.preview.setText("Corrige: "+str(exc))
            self.create.setEnabled(False)

    def generate(self):
        try:
            cfg=self.make_config()
            if self.root:
                regenerate_project(self.root,cfg)
            else:
                self.root=create_project(cfg)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self,"No se pudo crear la caja",str(exc))
            return
        self.accept()


def show_dialog(root=None):
    import FreeCADGui as Gui
    widget=PuzzleDialog(root,Gui.getMainWindow())
    widget.exec()


def _choose_export_folder(parent,title):
    folder=QtWidgets.QFileDialog.getExistingDirectory(parent,title)
    return folder or None


def _confirm_replace(parent,folder,names):
    if not any(os.path.exists(os.path.join(folder,name)) for name in names):
        return True
    answer=QtWidgets.QMessageBox.question(
        parent,"Sobrescribir archivos",
        "Ya existen STL o manifiestos con esos nombres. ¿Sobrescribir?",
        QtWidgets.QMessageBox.Yes|QtWidgets.QMessageBox.No)
    return answer==QtWidgets.QMessageBox.Yes


def export_parts(root):
    """Existing export keeps every part separately, now all at Z=0."""
    import FreeCADGui as Gui
    from . import print_plates
    parent=Gui.getMainWindow()
    folder=_choose_export_folder(parent,"Carpeta para STL separados")
    if not folder:
        return
    try:
        names=[key+".stl" for key,obj
               in print_plates._generated_objects(root)]
        if not _confirm_replace(parent,folder,names):
            return
        created=print_plates.export_separate(
            root,folder,keep_xy=hasattr(root,"RSMakerReliefSchema"))
    except Exception as exc:
        QtWidgets.QMessageBox.critical(parent,"Error exportando",str(exc))
        return
    QtWidgets.QMessageBox.information(
        parent,"Exportación completada",
        "%d STL individuales, cada pieza sobre Z=0. "
        "Revisa orientación y soportes en el laminador."%len(created))


def export_print_plates(root):
    """Pack pieces onto one or more STL printer beds (without moving CAD)."""
    import FreeCADGui as Gui
    from . import print_plates
    parent=Gui.getMainWindow()
    if hasattr(root,"RSMakerReliefSchema"):
        QtWidgets.QMessageBox.information(
            parent,"Usa exportar STL",
            "El modo platos está pensado para cajas puzzle. "
            "Las lámparas conservan sus STL separados.")
        return

    dialog=QtWidgets.QDialog(parent)
    dialog.setWindowTitle("Distribuir piezas en platos de impresión")
    form=QtWidgets.QFormLayout(dialog)
    def size_input(value,minval,maxval):
        spin=QtWidgets.QDoubleSpinBox(dialog)
        spin.setRange(minval,maxval)
        spin.setValue(value)
        spin.setDecimals(1)
        spin.setSuffix(" mm")
        return spin
    width=size_input(430,100,1000)
    depth=size_input(430,100,1000)
    gap=size_input(6,2,25)
    margin=size_input(8,3,30)
    form.addRow("Ancho de cama",width)
    form.addRow("Fondo de cama",depth)
    form.addRow("Separación mínima",gap)
    form.addRow("Margen exterior",margin)
    warning=QtWidgets.QLabel(
        "Distribuye la proyección XY original sin girar ni inclinar. "
        "Cada pieza queda apoyada en Z=0. Comprueba soportes y "
        "orientación de resistencia antes de imprimir.")
    warning.setWordWrap(True)
    form.addRow(warning)
    buttons=QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.Ok|QtWidgets.QDialogButtonBox.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    form.addRow(buttons)
    if dialog.exec()!=QtWidgets.QDialog.Accepted:
        return
    folder=_choose_export_folder(parent,"Elegir destino para los platos STL")
    if not folder:
        return
    try:
        generated=print_plates._generated_objects(root)
        dims=[]
        for key,obj in generated:
            bbox=obj.Shape.BoundBox
            dims.append((key,float(bbox.XMax-bbox.XMin),
                         float(bbox.YMax-bbox.YMin)))
        layout=print_plates.plan_plates(
            dims,width.value(),depth.value(),margin.value(),gap.value())
        names=["Plato_%02d.stl"%i
               for i in sorted({p.plate for p in layout})]
        names.append("Platos_RS_Maker.json")
        if not _confirm_replace(parent,folder,names):
            return
        result=print_plates.export_plates(
            root,folder,width.value(),depth.value(),
            margin.value(),gap.value())
    except Exception as exc:
        QtWidgets.QMessageBox.critical(
            parent,"No se pudieron crear los platos",str(exc))
        return
    QtWidgets.QMessageBox.information(
        parent,"Platos generados",
        "%d platos STL distribuidos con %d piezas. "
        "Consulta Platos_RS_Maker.json para ver qué contiene cada plato. "
        "El STL agrupa piezas separadas; comprueba el laminador."
        %(len(result["plates"]),len(generated)))
