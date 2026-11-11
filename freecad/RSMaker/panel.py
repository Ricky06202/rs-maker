"""FreeCAD native assistant: all five puzzles always present."""
import os
from dataclasses import replace
from .config import PuzzleConfig, PUZZLES, DIFFICULTIES, FACES, THEMES, DIAL_MARKS
from .collection import COLLECTIONS, FIGURES, SCENES, EXPRESSIONS
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
        self.setWindowTitle("RS Maker 0.3 | "+("Editar caja" if root else "Nueva caja de cinco puzzles"))
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
        note=QtWidgets.QLabel("Cuatro laterales: gira su rueda y mueve el cerrojo. "
                              "Tapa: gira la leva al final. La caja exige liberar los cinco seguros.")
        note.setWordWrap(True)
        main.addWidget(note)
        scroll=QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        container=QtWidgets.QWidget()
        body=QtWidgets.QVBoxLayout(container)

        lib=QtWidgets.QGroupBox("Biblioteca mecánica")
        lib_form=QtWidgets.QFormLayout(lib)
        self.library=QtWidgets.QComboBox()
        for key,item in PUZZLES.items():
            self.library.addItem(item["name"]+("" if item["implemented"] else " · En desarrollo"),key)
            if not item["implemented"]:
                idx=self.library.count()-1
                option=self.library.model().item(idx)
                if option is not None:
                    option.setEnabled(False)
        self.library.setToolTip("v0.3: un mecanismo lateral común; más familias se implementarán después")
        lib_form.addRow("Lateral disponible",self.library)
        top_info=QtWidgets.QLabel("La tapa siempre incluye un quinto puzzle de leva giratoria. "
                                  "Las opciones no implementadas están desactivadas.")
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
        tip=QtWidgets.QLabel("Comida añade relieves a las cuatro caras, "
            "una hamburguesita de una sola pieza y/o un restaurante con dos "
            "pivotes de montaje sobre la tapa. No sustituye el puzzle superior.")
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
        ti=self.theme.findData(cfg.theme)
        if ti >= 0:self.theme.setCurrentIndex(ti)
        self.sync_collection()

    def sync_collection(self):
        food=self.collection.currentData()=="Comida"
        self.figure.setEnabled(food)
        self.scene.setEnabled(food)
        self.expression.setEnabled(food and self.figure.currentData()!="Ninguna")
        self.figure_height.setEnabled(food and self.figure.currentData()!="Ninguna")
        self.theme.setEnabled(not food)

    def on_collection_changed(self,*args):
        food=self.collection.currentData()=="Comida"
        if food:
            self.theme.setCurrentIndex(self.theme.findData("Ninguno"))
            # First selection of a collection should show what it can make.
            if self.figure.currentData()=="Ninguna":
                self.figure.setCurrentIndex(self.figure.findData("Hamburguesita"))
            if self.scene.currentData()=="Ninguno":
                self.scene.setCurrentIndex(self.scene.findData("Restaurante"))
        else:
            self.figure.setCurrentIndex(self.figure.findData("Ninguna"))
            self.scene.setCurrentIndex(self.scene.findData("Ninguno"))
        self.sync_collection()
        self.update_preview()

    def make_config(self):
        args={name:inp.value() for name,inp in self.sizes.items()}
        args.update({name:inp.currentData() for name,inp in self.faces.items()})
        args["theme"]=self.theme.currentData()
        args.update({key:getattr(self,key).currentData()
                     for key in ("collection","expression")})
        food=args["collection"]=="Comida"
        args["figure"]=self.figure.currentData() if food else "Ninguna"
        args["scene"]=self.scene.currentData() if food else "Ninguno"
        args["figure_height"]=self.figure_height.value()
        return PuzzleConfig(**args).validate()

    def update_preview(self,*args):
        try:
            cfg=self.make_config()
            x,y,z=cfg.prize_interior
            self.sync_collection()
            art = (" · Figura: %s (%.1f mm) · Escena: %s" %
                   (cfg.figure,cfg.figure_height,cfg.scene) if cfg.collection=="Comida"
                   else " · Sin colección")
            self.preview.setText("5/5 caras activas · Espacio conservador del premio: "
                                 "%.1f × %.1f × %.1f mm.\n"
                                 "4 seguros laterales + 1 de tapa. "
                                 "El último cierre se resuelve al final%s. "
                                 "Tamaño mínimo de la caja actual: 150 mm, "
                                 "la versión compacta aún está pendiente."
                                 %(x,y,z,art))
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


def export_parts(root):
    import Mesh
    import FreeCADGui as Gui
    parent=Gui.getMainWindow()
    folder=QtWidgets.QFileDialog.getExistingDirectory(parent,"Carpeta para STL separados")
    if not folder:return
    generated=[o for o in root.Group if hasattr(o,"RSMakerPartKey")
               and hasattr(o,"Shape") and not o.Shape.isNull()]
    targets=[(o,os.path.join(folder,o.RSMakerPartKey+".stl")) for o in generated]
    if any(os.path.exists(path) for _,path in targets):
        yes=QtWidgets.QMessageBox.question(parent,"Archivos existentes",
             "Algunos STL existen. ¿Sobrescribirlos?",
             QtWidgets.QMessageBox.Yes|QtWidgets.QMessageBox.No)
        if yes!=QtWidgets.QMessageBox.Yes:return
    try:
        for obj,path in targets:
            Mesh.export([obj],path)
    except Exception as exc:
        QtWidgets.QMessageBox.critical(parent,"Error exportando",str(exc))
        return
    QtWidgets.QMessageBox.information(parent,"Exportación completada",
        "%d STL independientes creados. Orienta y distribuye las piezas en tu laminador."%len(targets))
