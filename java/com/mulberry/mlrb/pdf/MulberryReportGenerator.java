package com.mulberry.mlrb.pdf;

import com.itextpdf.kernel.colors.ColorConstants;
import com.itextpdf.kernel.colors.DeviceRgb;
import com.itextpdf.kernel.events.Event;
import com.itextpdf.kernel.events.IEventHandler;
import com.itextpdf.kernel.events.PdfDocumentEvent;
import com.itextpdf.kernel.geom.PageSize;
import com.itextpdf.kernel.geom.Rectangle;
import com.itextpdf.kernel.pdf.PdfDocument;
import com.itextpdf.kernel.pdf.PdfPage;
import com.itextpdf.kernel.pdf.PdfWriter;
import com.itextpdf.kernel.pdf.canvas.PdfCanvas;
import com.itextpdf.kernel.pdf.canvas.draw.SolidLine;
import com.itextpdf.layout.Document;
import com.itextpdf.layout.borders.Border;
import com.itextpdf.layout.element.Cell;
import com.itextpdf.layout.element.LineSeparator;
import com.itextpdf.layout.element.Paragraph;
import com.itextpdf.layout.element.Table;
import com.itextpdf.layout.properties.TextAlignment;
import com.itextpdf.layout.properties.UnitValue;

import java.io.IOException;
import java.util.List;

/**
 * Generator raport vehicul MLRB — A4, minimal alb/negru (Helvetica), structură tip factură.
 * <p>
 * Dependență Maven (iText 7; licență AGPL — comercial: licență iText SA sau folosește Apache PDFBox):
 * <pre>
 * {@code
 * <dependency>
 *   <groupId>com.itextpdf</groupId>
 *   <artifactId>itext7-core</artifactId>
 *   <version>8.0.5</version>
 *   <type>pom</type>
 * </dependency>
 * }
 * </pre>
 * Sau modulul kernel + layout separat, conform documentației iText.
 */
public class MulberryReportGenerator {

    /** Date vehicul — echivalent {@code VehicleReportData} Python / VehicleState frontend. */
    public static class VehicleData {
        private double velocityKmh;
        private double altitudeM;
        private double batteryPct;
        private boolean motorOn;
        private List<String> alerts;
        private String vin;
        private String modelLabel;

        public double getVelocityKmh() { return velocityKmh; }
        public void setVelocityKmh(double v) { this.velocityKmh = v; }
        public double getAltitudeM() { return altitudeM; }
        public void setAltitudeM(double altitudeM) { this.altitudeM = altitudeM; }
        public double getBatteryPct() { return batteryPct; }
        public void setBatteryPct(double batteryPct) { this.batteryPct = batteryPct; }
        public boolean isMotorOn() { return motorOn; }
        public void setMotorOn(boolean motorOn) { this.motorOn = motorOn; }
        public List<String> getAlerts() { return alerts; }
        public void setAlerts(List<String> alerts) { this.alerts = alerts; }
        public String getVin() { return vin; }
        public void setVin(String vin) { this.vin = vin; }
        public String getModelLabel() { return modelLabel; }
        public void setModelLabel(String modelLabel) { this.modelLabel = modelLabel; }
    }

    /**
     * Raport profesional A4; fundal off-white (#F7F7F5), text negru, Helvetica.
     */
    public void createProfessionalReport(String dest, VehicleData data, String reportId) throws IOException {
        PdfWriter writer = new PdfWriter(dest);
        PdfDocument pdf = new PdfDocument(writer);
        // Fundal off-white sub conținut (PlayerZero) — nu există setBackgroundColor pe Document în iText 7.
        pdf.addEventHandler(PdfDocumentEvent.START_PAGE, new IEventHandler() {
            @Override
            public void handleEvent(Event event) {
                PdfDocumentEvent ev = (PdfDocumentEvent) event;
                PdfPage page = ev.getPage();
                PdfDocument doc = page.getDocument();
                PdfCanvas canvas = new PdfCanvas(page.newContentStreamBefore(), page.getResources(), doc);
                Rectangle r = page.getPageSize();
                canvas.saveState();
                canvas.setFillColor(new DeviceRgb(247, 247, 245));
                canvas.rectangle(r);
                canvas.fill();
                canvas.restoreState();
            }
        });
        Document document = new Document(pdf, PageSize.A4);
        document.setMargins(48, 48, 48, 48);

        Table header = new Table(UnitValue.createPercentArray(new float[]{65f, 35f}));
        header.setWidth(UnitValue.createPercentValue(100));
        header.addCell(new Cell().add(new Paragraph("MULBERRY MLRB")
                        .setFontSize(22)
                        .setBold()
                        .setFontColor(ColorConstants.BLACK))
                .setBorder(Border.NO_BORDER));
        header.addCell(new Cell().add(new Paragraph("REPORT\n#" + reportId)
                        .setTextAlignment(TextAlignment.RIGHT)
                        .setFontSize(10)
                        .setBold()
                        .setFontColor(ColorConstants.BLACK))
                .setBorder(Border.NO_BORDER));
        document.add(header);

        SolidLine line = new SolidLine(1f);
        line.setColor(ColorConstants.BLACK);
        document.add(new LineSeparator(line).setMarginTop(14).setMarginBottom(14));

        document.add(new Paragraph("VEHICLE STATUS REPORT")
                .setBold()
                .setFontSize(13)
                .setMarginBottom(16));

        if (data.getVin() != null || data.getModelLabel() != null) {
            String meta = "";
            if (data.getVin() != null) meta += "VIN: " + data.getVin();
            if (data.getModelLabel() != null) {
                if (!meta.isEmpty()) meta += " · ";
                meta += data.getModelLabel();
            }
            document.add(new Paragraph(meta).setFontSize(10).setMarginBottom(14));
        }

        Table details = new Table(UnitValue.createPercentArray(new float[]{48f, 52f}));
        details.setWidth(UnitValue.createPercentValue(100));
        addRow(details, "Velocity", String.format("%.1f km/h", data.getVelocityKmh()));
        addRow(details, "Battery", String.format("%.1f %%", data.getBatteryPct()));
        addRow(details, "Altitude", String.format("%.1f m", data.getAltitudeM()));
        addRow(details, "Motor", data.isMotorOn() ? "ON" : "OFF");
        document.add(details.setMarginBottom(20));

        document.add(new Paragraph("Alerts").setBold().setFontSize(10).setMarginBottom(6));
        List<String> alerts = data.getAlerts();
        if (alerts == null || alerts.isEmpty()) {
            document.add(new Paragraph("— None").setFontSize(9));
        } else {
            for (String a : alerts) {
                document.add(new Paragraph("• " + a).setFontSize(9));
            }
        }

        document.close();
    }

    private static void addRow(Table table, String label, String value) {
        table.addCell(new Cell().add(new Paragraph(label).setFontSize(9))
                .setBorder(Border.NO_BORDER));
        table.addCell(new Cell().add(new Paragraph(value).setFontSize(11).setBold())
                .setBorder(Border.NO_BORDER));
    }
}
